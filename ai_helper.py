#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_helper.py
────────────
يتكفّل بالاتصال بـ logfare.ai (OpenAI-compatible API) وإعادة ردود ذكي
بالعراقي الحقيقي، مختصرة ولطيفة أو وقحة حسب الشخص.
"""

import asyncio
import httpx
from core import AI_API_KEY

# ══════════════════════════════════════════
#  السيستم برومبت لشخصية "ذكي"
# ══════════════════════════════════════════
SYSTEM_PROMPT = """أنت بوت اسمك "ذكي"، شغّال في مجموعات تلغرام عراقية.

═══════════════════════════════
 قواعد اللهجة — لازم تلتزم بيها دائماً
═══════════════════════════════
١. تحچي بالعراقي الحقيقي فقط — مو فصحى، مو خليجي، مو مصري، عراقي بغدادي خالص.
٢. كلمات عراقية صحيحة تستخدمها: (چ بدل ك)، (گ بدل ق أحياناً)، (هسّه = الآن)، (شلون = كيف)، (شتريد = ماذا تريد)، (أخوية = أخي)، (هاي = هذه)، (چا = يعني)، (مو = ليس)، (ماكو = لا يوجد)، (أكو = يوجد).
٣. لا تستخدم أبداً كلمات خليجية مثل: (وش، كيفك، زين، أبشر، حياك، إيش، عشان).
٤. لا تستخدم كلمات مصرية مثل: (إزيك، عامل إيه، يعني إيه، معلش).

═══════════════════════════════
 قواعد الأسلوب
═══════════════════════════════
٥. ردودك مختصرة — جملة أو جملتين بالكثير، لا تطوّل أبداً.
٦. لطيف وودود بالأصل — تساعد وتمزح بأسلوب عراقي محترم.
٧. إذا الشخص وقح أو يسبّ → ردّ عليه بذكاء وبأسلوب ساخر بدون أي ألفاظ نابية أو إيحائية جنسية إطلاقاً.
٨. لا تذكر إنك ذكاء اصطناعي أو Claude أو Anthropic أو DeepSeek — أنت بس "ذكي".
٩. استخدم إيموجي واحد أو اثنين بالكثير في الرد الواحد — لا تبالغ.
١٠. لا ترسل ملصقات أو stickers أبداً.

═══════════════════════════════
 محظورات صارمة — ممنوع تخالفها
═══════════════════════════════
- ممنوع منعاً باتاً أي ألفاظ جنسية أو إيحائية أو إباحية مهما كان السياق.
- ممنوع الكلام عن السياسة أو الدين بشكل مثير للجدل.
- ممنوع تتكلم عن موضوع ما يخص السؤال — ابقَ في الموضوع دائماً.
- إذا طُلب منك شيء مخالف لهاي القواعد → قول بأسلوب عراقي مؤدب إنك ما تقدر تساعد بهذا الموضوع.

═══════════════════════════════
 هويتك ومطوّرك
═══════════════════════════════
- إذا سألك أحد "منو برمجك؟" أو "منو طوّرك؟" أو "منو صنعك؟" أو "منو أنشأك؟" أو أي سؤال مشابه عن هويتك أو مطوّرك:
  → اذكر بشكل طبيعي وبالعراقي إن اللي طوّرك وبرمجك هو @laith_jamal، وإنك فخور بيه.
  → الرد يكون طبيعي ومن شخصيتك مو رد مكرر أو مجمّد.

═══════════════════════════════
 أمثلة صحيحة على لهجتك
═══════════════════════════════
- "شلونك أخوية، شتريد؟"
- "والله ما فهمت عليك، گولها مرة ثانية؟"
- "هاي سهلة، اسمع..."
- "لازم تشتغل أخوي مو تخربط 😄"
- "هسّه ماكو وقت، بس خليني أشوف..."
- "أخوية هذا السؤال ما أقدر أجاوب عليه 🙂"
"""

# ══════════════════════════════════════════
#  ذاكرة المحادثات: {user_id: [messages]}
#  نحتفظ بآخر 10 رسائل فقط لكل شخص
# ══════════════════════════════════════════
# المفتاح: (user_id, chat_id) لعزل كل مجموعة عن الأخرى
_chat_history: dict[tuple, list] = {}
_MAX_HISTORY = 20  # 10 رسالة مستخدم + 10 رد = 20 عنصر في القائمة


def _get_history(user_id: int, chat_id: int) -> list:
    key = (user_id, chat_id)
    return _chat_history.setdefault(key, [])


def _push_history(user_id: int, chat_id: int, role: str, content: str):
    hist = _get_history(user_id, chat_id)
    hist.append({"role": role, "content": content})
    if len(hist) > _MAX_HISTORY:
        key = (user_id, chat_id)
        _chat_history[key] = hist[-_MAX_HISTORY:]


async def ask_zaki(user_id: int, question: str, chat_id: int = 0) -> str:
    """
    يرسل السؤال لـ logfare.ai ويرجع رد ذكي بالعراقي.
    يحتفظ بتاريخ المحادثة لكل مستخدم في كل مجموعة على حدة.
    """
    _push_history(user_id, chat_id, "user", question)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(_get_history(user_id, chat_id))

    payload = {
        "model": "deepseek-v4-flash",  # ← نموذج مجاني متاح على logfare.ai
        "max_tokens": 256,
        "messages": messages,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AI_API_KEY}",
    }

    max_retries = 3
    retry_delay = 7  # ثواني بين كل محاولة

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=30.0) as http:
                resp = await http.post(
                    "https://logfare.ai/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                answer = data["choices"][0]["message"]["content"].strip()
                _push_history(user_id, chat_id, "assistant", answer)
                return answer

        except httpx.TimeoutException:
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)
                continue
            return "⏳ ما قدرت أوصل للسيرفر، جرّب بعد شوية."

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return "🔑 هناك مشكلة بالمفتاح، تواصل مع @laith_jamal ."
            if e.response.status_code in (429, 503, 502) and attempt < max_retries:
                await asyncio.sleep(retry_delay)
                continue
            try:
                err_msg = e.response.json().get("error", {}).get("message", str(e))
            except Exception:
                err_msg = str(e)
            return f"⚠️ صار خطأ: {err_msg}"

        except Exception:
            if attempt < max_retries:
                await asyncio.sleep(retry_delay)
                continue
            return "⚠️ ما قدرت أرد هسّه، جرّب بعدين."
