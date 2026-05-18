#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — utils | games | handlers_commands | handlers_messages | main
"""

import io
import re
import uuid
import random
import asyncio
import logging
import os
import tempfile
import subprocess
from datetime import datetime, timedelta, timezone

from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery, InlineQuery,
    InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions,
)
from pyrogram.enums import (
    MessageEntityType, ParseMode, ChatMembersFilter,
    ChatMemberStatus, ChatType,
)

from core import (
    BOT_TOKEN, API_ID, API_HASH, BOT_USERNAME, OWNER_ID, CHANNEL_ID,
    BIO_COMMANDS, PROFILE_COMMANDS, WELCOME_MESSAGES, BAD_WORDS,
    AMTHAL, QUIZ_DATA, RACE_PHRASES, HAQEEBA,
    get_db, _db_lock,
    db_get_user, db_get_settings, db_set_setting,
    db_add_mute, db_remove_mute, db_get_muted,
    db_add_warning, db_clear_warnings, db_get_warnings,
    db_log_punishment, db_get_punishments, db_get_rank,
    db_add_reply, db_get_reply, db_get_all_replies,
    db_delete_reply, db_find_reply_by_name,
    init_db, insert_trivia,
    db_audio_cache_get, db_audio_cache_set,
    guard,
    client_app as app,
    _user_sessions, group_games, WHISPERS_CACHE,
    XO_GAMES, XO_CHALLENGES,
    flood_cache, slow_mode_cache,
    pending_replies, pending_delete_replies, pending_auto_tag,
)

# ══════════════════ نظام التأهب ══════════════════
# {chat_id: {"active": bool, "minutes": int, "task": asyncio.Task|None, "last_admin_msg": datetime}}
_alert_state: dict = {}


async def _get_alert_state(chat_id: int) -> dict:
    if chat_id not in _alert_state:
        _alert_state[chat_id] = {"active": False, "minutes": 0, "task": None, "last_admin_msg": None}
    return _alert_state[chat_id]


async def _activate_full_protection(client, chat_id: int):
    """يقفل كل شيء على المميزين والأعضاء"""
    try:
        restricted = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        )
        await client.set_chat_permissions(chat_id, restricted)
        await client.send_message(
            chat_id,
            "🔴 <b>تم تفعيل وضع التأهب</b>\n\n"
            "الحماية الكاملة مفعّلة الآن:\n"
            "🔒 الروابط والمعرفات — مقفلة\n"
            "🔒 الوسائط بأنواعها — مقفلة\n"
            "🔒 التوجيه والفشار — مقفل\n\n"
            "⚠️ <i>لا يوجد مشرف نشط حالياً</i>",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logging.error(f"[تأهب] خطأ في تفعيل الحماية: {e}")


async def _deactivate_full_protection(client, chat_id: int):
    """يفتح الأقفال عند عودة المشرف"""
    try:
        normal = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        )
        await client.set_chat_permissions(chat_id, normal)
    except Exception as e:
        logging.error(f"[تأهب] خطأ في رفع الحماية: {e}")


async def _alert_watcher(client, chat_id: int, minutes: int):
    """يراقب غياب المشرفين ويفعّل الحماية عند الحاجة"""
    try:
        wait_seconds = minutes * 60
        await asyncio.sleep(wait_seconds)
        state = await _get_alert_state(chat_id)
        if not state["active"]:
            return
        # تحقق من آخر رسالة مشرف
        last = state.get("last_admin_msg")
        if last:
            elapsed = (datetime.now(timezone.utc) - last).total_seconds()
            if elapsed < wait_seconds - 5:
                # المشرف أرسل رسالة قريباً — لا تفعّل
                state["task"] = asyncio.get_event_loop().create_task(
                    _alert_watcher(client, chat_id, minutes)
                )
                return
        await _activate_full_protection(client, chat_id)
        # استمر في المراقبة
        state["task"] = asyncio.get_event_loop().create_task(
            _alert_watcher(client, chat_id, minutes)
        )
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logging.error(f"[تأهب] خطأ في المراقب: {e}")


# ══════════════════ UTILS ══════════════════

async def check_subscription(client: Client, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(CHANNEL_ID, user_id)
        return member.status in [
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
        ]
    except:
        return False


async def is_admin(client: Client, chat_id: int, user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]
    except:
        return False


async def get_bot_rank(client: Client, chat_id: int, user_id: int):
    if user_id == OWNER_ID:
        return 'المعمار', True
    try:
        m = await client.get_chat_member(chat_id, user_id)
        if m.status == ChatMemberStatus.OWNER:
            return 'مالك', True
        if m.status == ChatMemberStatus.ADMINISTRATOR:
            return 'مشرف', True
    except:
        pass
    rank = db_get_rank(user_id, chat_id)
    is_special = rank != 'عضو'
    return rank, is_special


def _extract_entity_text(text: str, entity) -> str:
    encoded = text.encode('utf-16-le')
    return encoded[entity.offset * 2:(entity.offset + entity.length) * 2].decode('utf-16-le')


async def get_target_from_args(client: Client, message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        return u.id, u.first_name
    if message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.TEXT_MENTION and entity.user:
                return entity.user.id, entity.user.first_name
            if entity.type == MessageEntityType.MENTION:
                username = _extract_entity_text(message.text, entity)
                try:
                    user = await client.get_users(username)
                    return user.id, user.first_name
                except Exception as e:
                    logging.warning(f"get_users failed for {username}: {e}")
                    await message.reply_text(
                        f"⚠️ تعذّر جلب بيانات {username}.\n"
                        "تأكد من صحة اليوزر أو استخدم الرد المباشر."
                    )
                    return None, None
    for w in (message.text or "").split():
        if w.startswith('@') and len(w) > 1:
            try:
                user = await client.get_users(w)
                return user.id, user.first_name
            except:
                await message.reply_text(
                    f"⚠️ تعذّر جلب بيانات {w}.\n"
                    "تأكد من صحة اليوزر أو استخدم الرد المباشر."
                )
                return None, None
    return None, None


async def get_members_by_rank(client: Client, chat_id: int, rank_name: str):
    """تجلب قائمة المستخدمين الذين لديهم رتبة معينة من جدول ranks."""
    with _db_lock:
        conn = get_db()
        rows = conn.execute(
            "SELECT user_id FROM ranks WHERE group_id=? AND rank=?",
            (chat_id, rank_name)
        ).fetchall()
        conn.close()
    
    members = []
    for row in rows:
        uid = row[0]
        try:
            member = await client.get_chat_member(chat_id, uid)
            user = member.user
            name = f"@{user.username}" if user.username else user.first_name or str(uid)
            members.append(name)
        except:
            members.append(str(uid))
    return members


async def get_random_member(client: Client, chat_id: int, exclude_user_id: int = None):
    """تختار عضواً عشوائياً من المجموعة (مع تخطي البوتات والمستثنى)."""
    import random
    members = []
    try:
        async for member in client.get_chat_members(chat_id):
            user = member.user
            if user.is_bot:
                continue
            if exclude_user_id and user.id == exclude_user_id:
                continue
            members.append(user)
    except Exception as e:
        logging.warning(f"فشل جلب الأعضاء: {e}")
        return None
    
    if not members:
        return None
    return random.choice(members)


async def auto_cleanup(client: Client, chat_id: int, *msg_ids):
    """تم تعطيل الحذف التلقائي — الرسائل تبقى دائماً."""
    pass


async def _get_profile_photo(client: Client, user_id: int):
    """إرجاع صورة البروفايل عبر file_id أو BytesIO كاحتياطي."""
    try:
        async for photo in client.get_chat_photos(user_id, limit=1):
            return photo.file_id
    except Exception as e:
        logging.warning(f"get_chat_photos فشل للمستخدم {user_id}: {e}")
    try:
        user = await client.get_chat(user_id)
        if user.photo:
            buf = await client.download_media(user.photo.big_file_id, in_memory=True)
            if buf:
                buf.seek(0)
                return buf
    except Exception as e:
        logging.warning(f"download_media فشل للمستخدم {user_id}: {e}")
    return None


async def _exec_admin_action(client, message, coro, success_text):
    """تنفيذ أمر إداري مع معالجة أخطاء الصلاحيات بشكل واضح."""
    try:
        await coro
        await message.reply_text(success_text)
        return True
    except Exception as e:
        err = str(e)
        if "CHAT_ADMIN_REQUIRED" in err or "not enough rights" in err.lower():
            await message.reply_text("⚠️ البوت ليس مشرفاً أو لا يملك الصلاحية الكافية لهذا الأمر.")
        elif "USER_ADMIN_INVALID" in err:
            await message.reply_text("⚠️ لا يمكن تنفيذ هذا الأمر على مشرف آخر.")
        elif "PEER_ID_INVALID" in err:
            await message.reply_text("⚠️ لم يتم العثور على المستخدم في هذه المجموعة.")
        else:
            await message.reply_text(
                f"⚠️ فشل تنفيذ الأمر:\n<code>{err[:200]}</code>",
                parse_mode=ParseMode.HTML
            )
        return False


# ══════════════════ GAMES ══════════════════

def _last_arabic_letter(word: str) -> str:
    word = re.sub(r'[^\u0621-\u064A]', '', word)
    if not word: return ''
    ch = word[-1]
    if ch == 'ة': ch = 'ه'
    if ch == 'ى': ch = 'ي'
    return ch


def _first_arabic_letter(word: str) -> str:
    word = re.sub(r'[^\u0621-\u064A]', '', word)
    if not word: return ''
    ch = word[0]
    if ch in 'أإآ': ch = 'ا'
    return ch


# ==================== كويز تفاعلي ====================

async def game_quiz_start(client: Client, message: Message):
    group_id = message.chat.id
    g = group_games.setdefault(group_id, {})
    if g.get('quiz', {}).get('active'):
        await message.reply_text("🎯 يوجد كويز نشط! انتظر انتهاءه.")
        return
    q   = random.choice(QUIZ_DATA)
    idx = list(range(4))
    random.shuffle(idx)
    shuffled    = [q['opts'][i] for i in idx]
    new_correct = idx.index(q['ans'])
    g['quiz'] = {
        'active': True, 'question': q['q'], 'opts': shuffled,
        'correct': new_correct, 'answerers': {}, 'started': datetime.now(),
    }
    labels  = ['🅐', '🅑', '🅒', '🅓']
    buttons = [
        [InlineKeyboardButton(f"{labels[i]}  {shuffled[i]}", callback_data=f"qz|{group_id}|{i}")]
        for i in range(4)
    ]
    msg = await message.reply_text(
        f"🎯 <b>كويز تفاعلي!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"❓ {q['q']}\n\n"
        f"📊 المجيبون: 0  ⏱ 30 ثانية\n"
        f"💰 كل إجابة صحيحة = عملة + 5 XP!",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    g['quiz']['msg_id'] = msg.id
    asyncio.create_task(_quiz_timeout(client, group_id, msg.id))


async def _quiz_timeout(client: Client, group_id: int, msg_id: int):
    await asyncio.sleep(30)
    g    = group_games.get(group_id, {})
    quiz = g.get('quiz')
    if not quiz or not quiz.get('active'):
        return
    correct_label = ['🅐', '🅑', '🅒', '🅓'][quiz['correct']]
    correct_opt   = quiz['opts'][quiz['correct']]
    winners       = [uid for uid, ch in quiz['answerers'].items() if ch == quiz['correct']]
    if winners:
        with _db_lock:
            conn = get_db()
            for uid in winners:
                conn.execute(
                    "UPDATE users SET coins=coins+1, xp=xp+5 WHERE user_id=? AND group_id=?",
                    (uid, group_id)
                )
            conn.commit()
            conn.close()
    win_text = f"🏆 أجاب صح {len(winners)} شخص!" if winners else "😢 لم يجب أحد بشكل صحيح"
    g['quiz'] = {}
    try:
        await client.edit_message_text(
            group_id, msg_id,
            f"🎯 <b>انتهى الكويز!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"❓ {quiz['question']}\n\n"
            f"✅ الإجابة: {correct_label} <b>{correct_opt}</b>\n{win_text}",
            parse_mode=ParseMode.HTML
        )
    except:
        pass


async def game_quiz_callback(client: Client, cq: CallbackQuery, group_id: int, choice: int):
    user_id = cq.from_user.id
    g       = group_games.get(group_id, {})
    quiz    = g.get('quiz')
    if not quiz or not quiz.get('active'):
        await cq.answer("⏰ انتهى الكويز!", show_alert=True)
        return
    if user_id in quiz['answerers']:
        await cq.answer("✋ أجبت مسبقاً!", show_alert=True)
        return
    quiz['answerers'][user_id] = choice
    is_correct = (choice == quiz['correct'])
    if is_correct:
        await cq.answer("✅ إجابة صحيحة! ربحت عملة 🎉", show_alert=True)
    else:
        await cq.answer("❌ إجابة خاطئة! حاول في الكويز القادم", show_alert=True)
    correct_count = sum(1 for ch in quiz['answerers'].values() if ch == quiz['correct'])
    total_count   = len(quiz['answerers'])
    labels  = ['🅐', '🅑', '🅒', '🅓']
    buttons = [
        [InlineKeyboardButton(f"{labels[i]}  {quiz['opts'][i]}", callback_data=f"qz|{group_id}|{i}")]
        for i in range(4)
    ]
    try:
        await cq.message.edit_text(
            f"🎯 <b>كويز تفاعلي!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"❓ {quiz['question']}\n\n"
            f"📊 المجيبون: {total_count}  ✅ صحيح: {correct_count}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except:
        pass


# ==================== كازينو ====================

async def game_casino(client: Client, message: Message, words: list):
    user_id  = message.from_user.id
    group_id = message.chat.id
    fname    = message.from_user.first_name or ""
    bet = 0
    for w in words[1:]:
        try: bet = int(w); break
        except: pass
    coins, _, _ = db_get_user(user_id, group_id, fname)
    if bet < 1:
        r = await message.reply_text(
            "🎰 <b>الكازينو</b>\n"
            "استخدم: <b>كازينو 2</b> (الرقم = رهانك)\n"
            "🏆 جاكبوت = 5 أضعاف الرهان!\n"
            "💎 ثلاثية = 3 أضعاف | 🍒 فوز = 2 أضعاف",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
        return
    if coins < bet:
        r = await message.reply_text(f"💸 رصيدك {coins} عملة، لا يكفي للرهان بـ {bet}!")
        asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
        return
    with _db_lock:
        conn = get_db()
        conn.execute(
            "UPDATE users SET coins=MAX(0,coins-?) WHERE user_id=? AND group_id=?",
            (bet, user_id, group_id)
        )
        conn.commit()
        conn.close()
    dice_msg = await client.send_dice(group_id, emoji="🎰")
    val = dice_msg.dice.value
    await asyncio.sleep(3)
    if val in [1, 22, 43, 64]:
        mult, icon, txt = 5, "🎰🎰🎰", "جاكبوت أسطوري!!!"
    elif val % 11 == 0:
        mult, icon, txt = 3, "💎💎💎", "ثلاثية ماسية!"
    elif val % 5 == 0:
        mult, icon, txt = 2, "🍒🍒", "فوز! أحسنت!"
    else:
        mult, icon, txt = 0, "💨", "خسرت! حظاً أوفر"
    win = bet * mult
    if win > 0:
        with _db_lock:
            conn = get_db()
            conn.execute(
                "UPDATE users SET coins=coins+? WHERE user_id=? AND group_id=?",
                (win, user_id, group_id)
            )
            conn.commit()
            conn.close()
    new_coins = max(0, coins - bet + win)
    await client.send_message(
        group_id,
        f"{icon} <b>{fname}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{txt}\n"
        f"{'🏆 ربحت ' + str(win) + ' عملة! (×' + str(mult) + ')' if win > 0 else '😢 خسرت ' + str(bet) + ' عملة'}\n"
        f"💰 رصيدك الآن: {new_coins} عملة",
        parse_mode=ParseMode.HTML
    )


# ==================== تحدي النرد PvP ====================

async def game_duel_start(client: Client, message: Message, words: list):
    group_id = message.chat.id
    user_id  = message.from_user.id
    fname    = message.from_user.first_name or ""
    g = group_games.setdefault(group_id, {})
    if g.get('duel', {}).get('active'):
        await message.reply_text("⚔️ يوجد تحدي نشط! انتظر انتهاءه.")
        return
    bet = 1
    for w in words[1:]:
        try: bet = max(1, int(w)); break
        except: pass
    coins, _, _ = db_get_user(user_id, group_id, fname)
    if coins < bet:
        r = await message.reply_text(f"💸 رصيدك {coins} عملة، لا يكفي للرهان بـ {bet}!")
        asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
        return
    g['duel'] = {
        'active': True, 'players': [{'id': user_id, 'name': fname}],
        'bet': bet, 'started': datetime.now(),
    }
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ قبول التحدي!", callback_data=f"duel|join|{group_id}")],
        [InlineKeyboardButton("❌ إلغاء",          callback_data=f"duel|cancel|{group_id}")],
    ])
    msg = await message.reply_text(
        f"⚔️ <b>تحدي النرد!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 {fname} يتحدى الجميع!\n"
        f"💰 الرهان: {bet} عملة\n\n"
        f"⏳ في انتظار منافس... (60 ثانية)",
        parse_mode=ParseMode.HTML, reply_markup=kb
    )
    g['duel']['msg_id'] = msg.id
    asyncio.create_task(_duel_timeout(client, group_id, msg.id))


async def _duel_timeout(client: Client, group_id: int, msg_id: int):
    await asyncio.sleep(60)
    g    = group_games.get(group_id, {})
    duel = g.get('duel')
    if not duel or not duel.get('active') or len(duel.get('players', [])) >= 2:
        return
    g['duel'] = {}
    try:
        await client.edit_message_text(
            group_id, msg_id,
            "⏰ <b>انتهى وقت التحدي!</b>\nلم يقبله أحد.",
            parse_mode=ParseMode.HTML
        )
    except:
        pass


async def game_duel_join(client: Client, cq: CallbackQuery, group_id: int):
    user_id = cq.from_user.id
    fname   = cq.from_user.first_name or ""
    g    = group_games.get(group_id, {})
    duel = g.get('duel')
    if not duel or not duel.get('active'):
        await cq.answer("⏰ التحدي انتهى!", show_alert=True)
        return
    if user_id == duel['players'][0]['id']:
        await cq.answer("❌ لا تتحدى نفسك!", show_alert=True)
        return
    if len(duel.get('players', [])) >= 2:
        await cq.answer("⚔️ التحدي ممتلئ!", show_alert=True)
        return
    bet     = duel['bet']
    coins, _, _ = db_get_user(user_id, group_id, fname)
    if coins < bet:
        await cq.answer(f"💸 رصيدك {coins} عملة، لا يكفي!", show_alert=True)
        return
    duel['active'] = False
    duel['players'].append({'id': user_id, 'name': fname})
    p1, p2 = duel['players']
    await cq.answer("⚔️ انضممت للتحدي!")
    try:
        await client.edit_message_text(
            group_id, duel['msg_id'],
            f"⚔️ <b>تحدي النرد!</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎲 {p1['name']}  vs  {p2['name']}\n"
            f"💰 الرهان: {bet} عملة\n\n🎲 جاري الرمي...",
            parse_mode=ParseMode.HTML
        )
    except:
        pass
    await asyncio.sleep(1)
    m1 = await client.send_dice(group_id, emoji="🎲")
    p1['roll'] = m1.dice.value
    await asyncio.sleep(2)
    m2 = await client.send_dice(group_id, emoji="🎲")
    p2['roll'] = m2.dice.value
    await asyncio.sleep(2)
    if p1['roll'] > p2['roll']:
        winner, loser = p1, p2
    elif p2['roll'] > p1['roll']:
        winner, loser = p2, p1
    else:
        await client.send_message(
            group_id,
            f"⚔️ <b>نتيجة التحدي</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"🎲 {p1['name']}: [{p1['roll']}]\n🎲 {p2['name']}: [{p2['roll']}]\n\n🤝 تعادل!",
            parse_mode=ParseMode.HTML
        )
        g['duel'] = {}
        return
    with _db_lock:
        conn = get_db()
        conn.execute(
            "UPDATE users SET coins=MAX(0,coins-?) WHERE user_id=? AND group_id=?",
            (bet, loser['id'], group_id)
        )
        conn.execute(
            "UPDATE users SET coins=coins+? WHERE user_id=? AND group_id=?",
            (bet, winner['id'], group_id)
        )
        conn.commit()
        conn.close()
    await client.send_message(
        group_id,
        f"⚔️ <b>نتيجة التحدي</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"🎲 {p1['name']}: [{p1['roll']}]\n🎲 {p2['name']}: [{p2['roll']}]\n\n"
        f"🏆 الفائز: <b>{winner['name']}</b> — ربح {bet} عملة من {loser['name']}!",
        parse_mode=ParseMode.HTML
    )
    g['duel'] = {}


async def game_duel_cancel(client: Client, cq: CallbackQuery, group_id: int):
    user_id = cq.from_user.id
    g    = group_games.get(group_id, {})
    duel = g.get('duel')
    if not duel or not duel.get('active'):
        await cq.answer("⏰ التحدي انتهى!", show_alert=True)
        return
    if duel['players'][0]['id'] != user_id and user_id != OWNER_ID:
        await cq.answer("❌ فقط منشئ التحدي يمكنه الإلغاء!", show_alert=True)
        return
    g['duel'] = {}
    await cq.answer("تم الإلغاء.")
    try:
        await cq.message.edit_text("❌ تم إلغاء التحدي.")
    except:
        pass


# ==================== كرة (بايسكتبول) ====================

async def game_kora(client: Client, message: Message, words: list):
    user_id  = message.from_user.id
    group_id = message.chat.id
    fname    = message.from_user.first_name or ""
    bet = 0
    for w in words[1:]:
        try: bet = int(w); break
        except: pass
    if bet < 1:
        r = await message.reply_text(
            "🏀 <b>تحدي الكرة</b>\nاستخدم: <b>كرة 2</b> (الرقم = رهانك)\n"
            "🎯 الدانك = ×2 | 💎 الثلاثية = ×3",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
        return
    coins, _, _ = db_get_user(user_id, group_id, fname)
    if coins < bet:
        r = await message.reply_text(f"💸 رصيدك {coins} عملة، لا يكفي!")
        asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
        return
    with _db_lock:
        conn = get_db()
        conn.execute(
            "UPDATE users SET coins=MAX(0,coins-?) WHERE user_id=? AND group_id=?",
            (bet, user_id, group_id)
        )
        conn.commit()
        conn.close()
    dice_msg = await client.send_dice(group_id, emoji="🏀")
    val = dice_msg.dice.value
    await asyncio.sleep(3)
    outcomes = {
        1: ("💨 فاتت! ضربت الهواء", 0),
        2: ("😅 على الطوق وما دخلت!", 0),
        3: ("🏀 دخلت! استرجاع الرهان", 1),
        4: ("🔥 دانك! ×2", 2),
        5: ("💎 ثلاثية أسطورية! ×3", 3),
    }
    desc, mult = outcomes.get(val, ("نتيجة غير محددة", 0))
    win = bet * mult
    if win > 0:
        with _db_lock:
            conn = get_db()
            conn.execute(
                "UPDATE users SET coins=coins+? WHERE user_id=? AND group_id=?",
                (win, user_id, group_id)
            )
            conn.commit()
            conn.close()
    new_coins = max(0, coins - bet + win)
    await client.send_message(
        group_id,
        f"🏀 <b>{fname}</b>\n━━━━━━━━━━━━━━━━━━\n{desc}\n"
        f"{'🏆 ربحت ' + str(win) + ' عملة!' if win > 0 else '😢 خسرت ' + str(bet) + ' عملة'}\n"
        f"💰 رصيدك: {new_coins} عملة",
        parse_mode=ParseMode.HTML
    )


# ==================== سباق الكتابة ====================

async def game_race_start(client: Client, message: Message):
    group_id = message.chat.id
    g = group_games.setdefault(group_id, {})
    if g.get('race', {}).get('active'):
        await message.reply_text("⚡ سباق نشط! اكتب الجملة أولاً.")
        return
    phrase = random.choice(RACE_PHRASES)
    g['race'] = {'active': True, 'phrase': phrase, 'started': datetime.now()}
    msg = await message.reply_text(
        f"⚡ <b>سباق الكتابة!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"اكتب الجملة التالية بالضبط:\n\n"
        f"📝 <code>{phrase}</code>\n\n"
        f"⏱ 45 ثانية فقط!\n"
        f"🥇 أول من يكتبها = 3 عملات!",
        parse_mode=ParseMode.HTML
    )
    g['race']['msg_id'] = msg.id
    asyncio.create_task(_race_timeout(client, group_id, msg.id, phrase))


async def _race_timeout(client: Client, group_id: int, msg_id: int, phrase: str):
    await asyncio.sleep(45)
    g    = group_games.get(group_id, {})
    race = g.get('race')
    if not race or not race.get('active'):
        return
    g['race'] = {}
    try:
        await client.edit_message_text(
            group_id, msg_id,
            f"⏰ <b>انتهى وقت السباق!</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"الجملة كانت:\n<code>{phrase}</code>\n\nاكتب <b>سباق</b> للمحاولة مجدداً!",
            parse_mode=ParseMode.HTML
        )
    except:
        pass


async def game_race_check(client: Client, message: Message) -> bool:
    group_id = message.chat.id
    g        = group_games.get(group_id, {})
    race     = g.get('race')
    if not race or not race.get('active'):
        return False
    if datetime.now() - race['started'] > timedelta(seconds=45):
        g['race'] = {}
        return False
    if message.text.strip() != race['phrase'].strip():
        return False
    user_id = message.from_user.id
    fname   = message.from_user.first_name or ""
    with _db_lock:
        conn = get_db()
        conn.execute(
            "UPDATE users SET coins=coins+3 WHERE user_id=? AND group_id=?",
            (user_id, group_id)
        )
        conn.commit()
        conn.close()
    msg_id = race.get('msg_id')
    g['race'] = {}
    if msg_id:
        try: await client.delete_messages(group_id, msg_id)
        except: pass
    await message.reply_text(
        f"⚡ <b>🥇 فاز {fname}!</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"✅ كتب الجملة بشكل صحيح!\n🏆 ربح 3 عملات!",
        parse_mode=ParseMode.HTML
    )
    return True


# ==================== الوصلة الجماعية ====================

async def game_waslah_start(client: Client, message: Message):
    group_id = message.chat.id
    g = group_games.setdefault(group_id, {})
    if g.get('waslah', {}).get('active'):
        cur     = g['waslah']['last_word']
        last_ch = _last_arabic_letter(cur)
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("⛔ إنهاء الوصلة", callback_data=f"waslah|end|{group_id}")
        ]])
        await message.reply_text(
            f"🔗 الوصلة نشطة!\nالكلمة الأخيرة: <b>{cur}</b>\nابدأ بحرف: <b>{last_ch}</b>",
            parse_mode=ParseMode.HTML, reply_markup=kb
        )
        return
    start_words = ["سماء","بحر","قمر","شمس","نهر","جبل","عقل","علم","كتاب","صوت","نور","قلب"]
    first   = random.choice(start_words)
    last_ch = _last_arabic_letter(first)
    g['waslah'] = {
        'active': True, 'last_word': first, 'last_user': None,
        'used': {first}, 'started': datetime.now(),
    }
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("⛔ إنهاء الوصلة", callback_data=f"waslah|end|{group_id}")
    ]])
    await message.reply_text(
        "🔗 <b>لعبة الوصلة بدأت!</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"الكلمة الأولى: <b>{first}</b>\nابدأ بحرف: <b>{last_ch}</b>\n\n"
        "📌 كلمة عربية واحدة تبدأ بآخر حرف الكلمة السابقة\n💰 كل 5 كلمات = عملة!",
        parse_mode=ParseMode.HTML, reply_markup=kb
    )


async def game_waslah_check(client: Client, message: Message) -> bool:
    group_id = message.chat.id
    g        = group_games.get(group_id, {})
    waslah   = g.get('waslah')
    if not waslah or not waslah.get('active'):
        return False
    user_id = message.from_user.id
    text    = message.text.strip()
    if not re.match(r'^[\u0621-\u064A]+$', text):
        return False
    last_ch  = _last_arabic_letter(waslah['last_word'])
    first_ch = _first_arabic_letter(text)
    if first_ch != last_ch:
        r = await message.reply_text(
            f"❌ الكلمة يجب تبدأ بـ <b>{last_ch}</b>!", parse_mode=ParseMode.HTML
        )
        asyncio.create_task(auto_cleanup(client, group_id, r.id))
        return True
    if text in waslah['used']:
        r = await message.reply_text("❌ هذه الكلمة ذُكرت! اختر غيرها.")
        asyncio.create_task(auto_cleanup(client, group_id, r.id))
        return True
    waslah['last_word'] = text
    waslah['last_user'] = user_id
    waslah['used'].add(text)
    count  = len(waslah['used']) - 1
    reward = ""
    if count % 5 == 0:
        with _db_lock:
            conn = get_db()
            conn.execute(
                "UPDATE users SET coins=coins+1 WHERE user_id=? AND group_id=?",
                (user_id, group_id)
            )
            conn.commit()
            conn.close()
        reward = " 🎁 +عملة!"
    next_ch = _last_arabic_letter(text)
    await message.reply_text(
        f"✅ <b>{text}</b> — التالي: <b>{next_ch}</b> | {count} كلمة{reward}",
        parse_mode=ParseMode.HTML
    )
    return True


# ==================== أكمل المثل ====================

async def game_mathal_start(client: Client, message: Message):
    group_id = message.chat.id
    g = group_games.setdefault(group_id, {})
    if g.get('mathal', {}).get('active'):
        await message.reply_text("🧐 يوجد مثل نشط! أكمله أولاً.")
        return
    q, a = random.choice(AMTHAL)
    g['mathal'] = {
        'active': True, 'answer': a, 'question': q,
        'started': datetime.now(), 'hints': 0,
    }
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("💡 مساعدة (حرف)", callback_data=f"hint|{group_id}")
    ]])
    await message.reply_text(
        f"📖 <b>أكمل المثل:</b>\n\n❝ {q} ... ❞\n\n"
        f"⏱ دقيقتان! 💰 أول مجيب = عملة",
        parse_mode=ParseMode.HTML, reply_markup=kb
    )


async def game_mathal_hint(client: Client, cq: CallbackQuery, group_id: int):
    g      = group_games.get(group_id, {})
    mathal = g.get('mathal')
    if not mathal or not mathal.get('active'):
        await cq.answer("⏰ انتهى المثل!", show_alert=True)
        return
    answer = mathal['answer']
    hints  = mathal.get('hints', 0)
    if hints >= len(answer):
        await cq.answer("✅ تمّ الكشف عن كل الحروف!", show_alert=True)
        return
    mathal['hints'] += 1
    revealed = answer[:mathal['hints']] + '_ ' * (len(answer) - mathal['hints'])
    await cq.answer(f"💡 المساعدة: {revealed}", show_alert=True)


async def game_mathal_check(client: Client, message: Message) -> bool:
    group_id = message.chat.id
    g        = group_games.get(group_id, {})
    mathal   = g.get('mathal')
    if not mathal or not mathal.get('active'):
        return False
    if datetime.now() - mathal['started'] > timedelta(minutes=2):
        g['mathal'] = {}
        return False
    user_answer = message.text.strip()
    correct     = mathal['answer'].strip()
    if user_answer != correct:
        return False
    user_id = message.from_user.id
    fname   = message.from_user.first_name or ""
    group_id = message.chat.id
    with _db_lock:
        conn = get_db()
        conn.execute(
            "UPDATE users SET coins=coins+1 WHERE user_id=? AND group_id=?",
            (user_id, group_id)
        )
        conn.commit()
        conn.close()
    g['mathal'] = {}
    await message.reply_text(
        f"🎉 <b>{fname}</b> أكمل المثل صح!\n"
        f"✅ «{mathal['question']} <b>{correct}</b>»\n"
        f"🏆 ربح عملة!",
        parse_mode=ParseMode.HTML
    )
    return True


# ==================== لعبة XO ====================

def _check_xo_winner(board):
    wins = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
    for a, b, c in wins:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None


def _xo_bot_move(board, bot_sym, player_sym):
    """البوت يختار أفضل حركة (يمنع، يفوز، أو يعشوائي)."""
    for sym in [bot_sym, player_sym]:
        for i in range(9):
            if board[i] is None:
                board[i] = sym
                if _check_xo_winner(board):
                    board[i] = None
                    return i
                board[i] = None
    center = 4
    if board[center] is None:
        return center
    corners = [i for i in [0, 2, 6, 8] if board[i] is None]
    if corners:
        return random.choice(corners)
    sides = [i for i in [1, 3, 5, 7] if board[i] is None]
    if sides:
        return random.choice(sides)
    return None


def _xo_markup(board, finished=False):
    emojis = {'X': '❌', 'O': '⭕'}
    btns   = []
    for row_start in range(0, 9, 3):
        row = []
        for idx in range(row_start, row_start + 3):
            symbol = emojis.get(board[idx], '▫️') if board[idx] else '▫️'
            row.append(InlineKeyboardButton(
                symbol,
                callback_data=f"xo_play|{idx}" if not finished else "xo_done"
            ))
        btns.append(row)
    if finished:
        btns.append([InlineKeyboardButton("🔄 العب مجدداً", callback_data="xo_restart")])
    btns.append([InlineKeyboardButton("🚫 استسلام", callback_data="xo_surrender")])
    return InlineKeyboardMarkup(btns)


async def game_xo_start(client: Client, message: Message):
    user_id  = message.from_user.id
    group_id = message.chat.id
    fname    = message.from_user.first_name or ""
    words_xo = message.text.strip().split()
    t_id, t_name = None, None
    if len(words_xo) > 1:
        for w in words_xo[1:]:
            if w.startswith('@') and len(w) > 1:
                try:
                    user = await client.get_users(w)
                    if user.id != user_id and user.id != client.me.id:
                        t_id   = user.id
                        t_name = user.first_name
                    break
                except:
                    pass
    if t_id:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ قبول التحدي", callback_data=f"xo_accept|{user_id}|{t_id}")],
            [InlineKeyboardButton("❌ رفض التحدي",  callback_data="xo_decline")],
        ])
        msg = await message.reply_text(
            f"⚔️ <b>تحدي XO!</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"🎯 {fname} يتحدى {t_name}!\n"
            f"🎲 الفائز يربح <b>عملة واحدة</b>\n\n"
            f"⏳ بانتظار قبول {t_name}... (60 ثانية)",
            parse_mode=ParseMode.HTML, reply_markup=kb
        )
        XO_CHALLENGES[msg.id] = {
            'from_user': user_id, 'to_user': t_id,
            'from_name': fname, 'to_name': t_name, 'started': datetime.now(),
        }
        asyncio.create_task(_xo_challenge_timeout(client, group_id, msg.id))
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎮 اقبل التحدي!", callback_data=f"xo_accept_any|{user_id}")],
        [InlineKeyboardButton("🤖 العب مع ذكي",  callback_data=f"xo_bot|{user_id}")],
    ])
    msg = await message.reply_text(
        f"🎮 <b>تحدي XO!</b>\n━━━━━━━━━━━━━━━━━━\n"
        f"🎯 {fname} يبحث عن منافس!\n"
        f"🎲 الفائز يربح <b>عملة واحدة</b>\n\n"
        f"⏳ بانتظار منافس... (60 ثانية)",
        parse_mode=ParseMode.HTML, reply_markup=kb
    )
    XO_CHALLENGES[msg.id] = {
        'from_user': user_id, 'to_user': None,
        'from_name': fname, 'started': datetime.now(),
    }
    asyncio.create_task(_xo_challenge_timeout(client, group_id, msg.id))


async def _xo_challenge_timeout(client: Client, group_id: int, msg_id: int):
    await asyncio.sleep(60)
    if msg_id in XO_CHALLENGES:
        XO_CHALLENGES.pop(msg_id)
        try:
            await client.edit_message_text(
                group_id, msg_id,
                "⏰ <b>انتهى وقت التحدي!</b>\n"
                "لم يقبله أحد. يمكنك إرسال <b>XO</b> مجدداً.",
                parse_mode=ParseMode.HTML
            )
        except:
            pass


async def _xo_accept_challenge(client: Client, cq: CallbackQuery, opponent_id: int):
    user_id = cq.from_user.id
    if user_id != opponent_id:
        await cq.answer("❌ هذا التحدي ليس لك!", show_alert=True)
        return
    msg = cq.message
    if msg.id not in XO_CHALLENGES:
        await cq.answer("⏰ انتهى التحدي!", show_alert=True)
        return
    challenge = XO_CHALLENGES.pop(msg.id)
    await _xo_start_game(
        client, cq.message,
        challenge['from_user'], challenge['from_name'],
        challenge['to_user'], challenge['to_name']
    )


async def _xo_accept_any(client: Client, cq: CallbackQuery, from_user_id: int):
    user_id = cq.from_user.id
    if user_id == from_user_id:
        await cq.answer("❌ لا يمكنك تحدي نفسك!", show_alert=True)
        return
    msg = cq.message
    if msg.id not in XO_CHALLENGES:
        await cq.answer("⏰ انتهى التحدي!", show_alert=True)
        return
    challenge = XO_CHALLENGES.pop(msg.id)
    await _xo_start_game(
        client, cq.message,
        from_user_id, challenge['from_name'],
        user_id, cq.from_user.first_name or ""
    )


async def _xo_start_bot(client: Client, cq: CallbackQuery, from_user_id: int):
    user_id = cq.from_user.id
    if user_id != from_user_id:
        await cq.answer("❌ هذا ليس تحديك!", show_alert=True)
        return
    msg = cq.message
    if msg.id not in XO_CHALLENGES:
        await cq.answer("⏰ انتهى التحدي!", show_alert=True)
        return
    challenge = XO_CHALLENGES.pop(msg.id)
    await _xo_start_game(
        client, cq.message,
        from_user_id, challenge['from_name'],
        client.me.id, "البوت 🤖", is_bot=True
    )


async def _xo_start_game(client, message, p1_id, p1_name, p2_id, p2_name, is_bot=False):
    board     = [None] * 9
    game_text = (
        f"⚔️ <b>XO!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"❌ {p1_name}  vs  ⭕ {p2_name}\n"
        f"🎯 الدور على: <b>{p1_name}</b>\n"
        f"🎲 الرهان: <b>عملة واحدة</b>"
    )
    try:
        game_msg = await message.edit_text(
            game_text, parse_mode=ParseMode.HTML, reply_markup=_xo_markup(board)
        )
    except Exception:
        game_msg = await message.reply_text(
            game_text, parse_mode=ParseMode.HTML, reply_markup=_xo_markup(board)
        )
    XO_GAMES[game_msg.id] = {
        'board': board, 'p1_id': p1_id, 'p2_id': p2_id,
        'p1_name': p1_name, 'p2_name': p2_name,
        'current_turn': p1_id, 'is_bot': is_bot,
        'finished': False, 'bot_thinking': False,
        'chat_id': message.chat.id,
    }


async def _xo_bot_play(client, msg_id):
    game = XO_GAMES.get(msg_id)
    if not game or game['finished']:
        return
    if game.get('bot_thinking'):
        return
    game['bot_thinking'] = True
    try:
        await asyncio.sleep(1.5)
        game = XO_GAMES.get(msg_id)
        if not game or game['finished']:
            return
        board = game['board']
        move  = _xo_bot_move(board, 'O', 'X')
        if move is None:
            return
        board[move] = 'O'
        await _xo_check_winner(client, msg_id)
    finally:
        game = XO_GAMES.get(msg_id)
        if game:
            game['bot_thinking'] = False


async def _xo_play(client: Client, cq: CallbackQuery, idx: int):
    user_id = cq.from_user.id
    msg_id  = cq.message.id
    game    = XO_GAMES.get(msg_id)
    if not game or game['finished']:
        await cq.answer("⏰ انتهت اللعبة!", show_alert=True)
        return
    if user_id != game['p1_id'] and user_id != game['p2_id']:
        await cq.answer("🚫 هذه اللعبة ليست لك! يمكنك بدء واحدة جديدة بواسطة الأمر XO.", show_alert=True)
        return
    if user_id != game['current_turn']:
        await cq.answer("⏳ ليس دورك الآن! انتظر دورك.", show_alert=True)
        return
    board = game['board']
    if board[idx] is not None:
        await cq.answer("📦 هذه الخانة محجوزة!", show_alert=True)
        return
    symbol    = 'X' if user_id == game['p1_id'] else 'O'
    board[idx] = symbol
    await _xo_check_winner(client, msg_id, cq=cq)


async def _xo_check_winner(client, msg_id, cq=None):
    game = XO_GAMES.get(msg_id)
    if not game:
        return
    board   = game['board']
    winner  = _check_xo_winner(board)
    is_full = all(cell is not None for cell in board)
    chat_id = game['chat_id']
    if winner or is_full:
        game['finished'] = True
        if winner:
            winner_id   = game['p1_id'] if winner == 'X' else game['p2_id']
            loser_id    = game['p2_id'] if winner == 'X' else game['p1_id']
            winner_name = game['p1_name'] if winner == 'X' else game['p2_name']
            if not game.get('is_bot'):
                with _db_lock:
                    conn = get_db()
                    conn.execute(
                        "UPDATE users SET coins=coins+1 WHERE user_id=? AND group_id=?",
                        (winner_id, chat_id)
                    )
                    conn.execute(
                        "UPDATE users SET coins=MAX(0,coins-1) WHERE user_id=? AND group_id=?",
                        (loser_id, chat_id)
                    )
                    conn.commit()
                    conn.close()
            try:
                await client.edit_message_text(
                    chat_id, msg_id,
                    f"🏆 <b>{winner_name} فاز!</b>\n━━━━━━━━━━━━━━━━━━\n"
                    f"❌ {game['p1_name']}  vs  ⭕ {game['p2_name']}\n"
                    f"🎉 الفائز ربح <b>عملة واحدة</b>!",
                    parse_mode=ParseMode.HTML,
                    reply_markup=_xo_markup(board, finished=True)
                )
            except:
                pass
        else:
            try:
                await client.edit_message_text(
                    chat_id, msg_id,
                    f"🤝 <b>تعادل!</b>\n━━━━━━━━━━━━━━━━━━\n"
                    f"❌ {game['p1_name']}  vs  ⭕ {game['p2_name']}\n"
                    "تم إرجاع الرهان للطرفين.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=_xo_markup(board, finished=True)
                )
            except:
                pass
    else:
        game['current_turn'] = game['p2_id'] if game['current_turn'] == game['p1_id'] else game['p1_id']
        next_name = game['p1_name'] if game['current_turn'] == game['p1_id'] else game['p2_name']
        try:
            await client.edit_message_text(
                chat_id, msg_id,
                f"⚔️ <b>XO!</b>\n━━━━━━━━━━━━━━━━━━\n"
                f"❌ {game['p1_name']}  vs  ⭕ {game['p2_name']}\n"
                f"🎯 الدور على: <b>{next_name}</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=_xo_markup(board)
            )
        except:
            pass
        if game.get('is_bot') and game['current_turn'] == game['p2_id']:
            await asyncio.sleep(1)
            await _xo_bot_play(client, msg_id)


async def _xo_surrender(client: Client, cq: CallbackQuery):
    user_id = cq.from_user.id
    msg_id  = cq.message.id
    game    = XO_GAMES.get(msg_id)
    if not game or game['finished']:
        await cq.answer("⏰ انتهت اللعبة!", show_alert=True)
        return
    if user_id not in [game['p1_id'], game['p2_id']]:
        await cq.answer("❌ أنت لست لاعباً في هذه المباراة!", show_alert=True)
        return
    winner_name = game['p2_name'] if user_id == game['p1_id'] else game['p1_name']
    game['finished'] = True
    try:
        await cq.message.edit_text(
            f"🏳️ <b>استسلام!</b>\n{winner_name} فاز!\n━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML
        )
    except:
        pass


async def _xo_restart(client: Client, cq: CallbackQuery):
    msg_id   = cq.message.id
    old_game = XO_GAMES.get(msg_id)
    if not old_game:
        await cq.answer("ابدأ لعبة جديدة بإرسال XO في المجموعة", show_alert=True)
        return
    p1_id   = old_game['p1_id'];   p1_name = old_game['p1_name']
    p2_id   = old_game['p2_id'];   p2_name = old_game['p2_name']
    is_bot  = old_game.get('is_bot', False)
    chat_id = old_game['chat_id']
    board   = [None] * 9
    XO_GAMES[msg_id] = {
        'board': board, 'p1_id': p1_id, 'p2_id': p2_id,
        'p1_name': p1_name, 'p2_name': p2_name,
        'current_turn': p1_id, 'is_bot': is_bot,
        'finished': False, 'bot_thinking': False, 'chat_id': chat_id,
    }
    await cq.answer("🔄 بدأت لعبة جديدة!")
    try:
        await cq.message.edit_text(
            f"⚔️ <b>XO!</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"❌ {p1_name}  vs  ⭕ {p2_name}\n"
            f"🎯 الدور على: <b>{p1_name}</b>\n"
            f"🎲 الرهان: <b>عملة واحدة</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=_xo_markup(board)
        )
    except:
        pass


# ══════════════════ HANDLERS COMMANDS ══════════════════

async def cmd_profile(client: Client, message: Message):
    group_id = message.chat.id
    t_id, _  = await get_target_from_args(client, message)
    user_id  = t_id if t_id else message.from_user.id

    username = "لا يوجد"
    try:
        cm       = await client.get_chat_member(group_id, user_id)
        username = f"@{cm.user.username}" if cm.user.username else "لا يوجد"
    except:
        pass

    coins, msg_count, _ = db_get_user(user_id, group_id)
    rank, _  = await get_bot_rank(client, group_id, user_id)
    settings = db_get_settings(str(group_id))
    warns    = db_get_warnings(user_id, group_id)

    caption = (
        "💠 ❪ 𝗣𝗥𝗢𝗙𝗜𝗟𝗘 ❫ 💠\n"
        "▱▱▱▱▱▱▱▱▱▱\n"
        f"🆔 ⦇ الايدي ⦈ : <code>{user_id}</code>\n"
        f"🔖 ⦇ اليوزر ⦈ : {username}\n"
        "▱▱▱▱▱▱▱▱▱▱\n"
        f"👑 ⦇ الرتبة ⦈ : {rank}\n"
        f"💰 ⦇ العملات ⦈ : {coins}\n"
        f"💬 ⦇ التفاعل ⦈ : {msg_count} رسالة\n"
        f"⚠️ ⦇ التحذيرات ⦈ : {warns}/3\n"
        "▱▱▱▱▱▱▱▱▱▱"
    )
    caption_no_photo = caption + "\n👤 <i>الصورة مخفية أو محمية بإعدادات الخصوصية</i>"

    reply_msg = None
    if settings['photo'] == 1:
        photo_buf = await _get_profile_photo(client, user_id)
        if photo_buf:
            try:
                reply_msg = await message.reply_photo(
                    photo_buf, caption=caption, parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logging.warning(f"فشل إرسال صورة البروفايل للمستخدم {user_id}: {e}")
        if not reply_msg:
            reply_msg = await message.reply_text(caption_no_photo, parse_mode=ParseMode.HTML)
    if not reply_msg:
        reply_msg = await message.reply_text(caption, parse_mode=ParseMode.HTML)
    asyncio.create_task(auto_cleanup(client, group_id, message.id, reply_msg.id))


async def cmd_bio(client: Client, message: Message):
    group_id = message.chat.id
    t_id, _  = await get_target_from_args(client, message)
    user_id  = t_id if t_id else message.from_user.id
    try:
        chat_obj = await client.get_chat(user_id)
        bio_text = chat_obj.bio
    except:
        bio_text = None
    if bio_text:
        r = await message.reply_text(
            f"📝 <b>نبذة الشخص:</b>\n\n{bio_text}", parse_mode=ParseMode.HTML
        )
    else:
        r = await message.reply_text(
            f"⚠️ <b>لا توجد نبذة أو تعذّر جلبها.</b>\n\n"
            f"👉 افتح محادثة خاصة مع @{BOT_USERNAME} واضغط Start.",
            parse_mode=ParseMode.HTML
        )
    asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))


# ==================== أوامر إدارية مساعدة ====================

async def cmd_muted_list(client: Client, message: Message):
    group_id   = message.chat.id
    muted_list = db_get_muted(group_id)
    if not muted_list:
        await message.reply_text("📋 لا يوجد أي عضو مكتوم حالياً.")
        return
    text = f"📋 <b>المكتومون ({len(muted_list)}):</b>\n━━━━━━━━━━━━━━━━━━\n"
    for uid in muted_list[:20]:
        try:
            m    = await client.get_chat_member(group_id, uid)
            name = f"@{m.user.username}" if m.user.username else m.user.first_name
        except:
            name = str(uid)
        text += f"• {name}\n"
    await message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_clear_mutes(client: Client, message: Message):
    group_id   = message.chat.id
    muted_list = db_get_muted(group_id)
    count = 0
    for uid in muted_list:
        try:
            await client.restrict_chat_member(
                group_id, uid,
                ChatPermissions(
                    can_send_messages=True, can_send_media_messages=True,
                    can_send_polls=True, can_add_web_page_previews=True,
                    can_invite_users=True,
                )
            )
            db_remove_mute(uid, group_id)
            count += 1
        except:
            pass
    await message.reply_text(f"✅ تم إلغاء كتم {count} عضو.")


async def cmd_punishments(client: Client, message: Message, for_self=False):
    group_id = message.chat.id
    if for_self:
        user_id = message.from_user.id
        label   = "عقوباتك"
    else:
        t_id, t_name = await get_target_from_args(client, message)
        if not t_id:
            await message.reply_text("⚠️ حدد عضواً.")
            return
        user_id = t_id
        label   = f"عقوبات {t_name}"
    rows = db_get_punishments(user_id, group_id)
    if not rows:
        await message.reply_text(f"📋 لا توجد عقوبات مسجلة لـ {label}.")
        return
    text = f"📋 <b>{label}:</b>\n━━━━━━━━━━━━━━━━━━\n"
    for action, ts in rows:
        text += f"• {action} — {ts}\n"
    await message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_group_stats(client: Client, message: Message):
    group_id = message.chat.id
    try:
        chat          = await client.get_chat(group_id)
        members_count = chat.members_count or 0
    except:
        members_count = 0
    admin_count = 0
    try:
        async for _ in client.get_chat_members(group_id, filter=ChatMembersFilter.ADMINISTRATORS):
            admin_count += 1
    except:
        pass
    muted_count = len(db_get_muted(group_id))
    await message.reply_text(
        "📊 <b>إحصائيات المجموعة</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👥 الأعضاء : {members_count:,}\n"
        f"⚙️ المشرفون : {admin_count}\n"
        f"🔇 المكتومون : {muted_count}\n"
        "━━━━━━━━━━━━━━━━━━",
        parse_mode=ParseMode.HTML
    )


# ==================== نظام الهمسة ====================

async def cmd_whisper(client: Client, message: Message):
    group_id = message.chat.id
    user_id  = message.from_user.id
    fname    = message.from_user.first_name or ""

    settings = db_get_settings(str(group_id))
    if settings.get('whisper', 1) == 0:
        r = await message.reply_text("🔇 الهمسة معطّلة في هذه المجموعة.")
        asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
        return

    target_id   = None
    target_name = None

    if message.reply_to_message and message.reply_to_message.from_user:
        ru = message.reply_to_message.from_user
        if ru.is_bot:
            r = await message.reply_text("⚠️ لا يمكنك الهمس للبوت!")
            asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
            return
        target_id   = ru.id
        target_name = ru.first_name or str(ru.id)
    else:
        text  = message.text.strip()
        parts = text.split(None, 1)
        if len(parts) >= 2:
            mention_raw = parts[1].strip().lstrip('@')
            try:
                user_obj    = await client.get_users(mention_raw)
                target_id   = user_obj.id
                target_name = user_obj.first_name or mention_raw
            except:
                if message.entities:
                    for ent in message.entities:
                        if ent.type == MessageEntityType.TEXT_MENTION and ent.user:
                            target_id   = ent.user.id
                            target_name = ent.user.first_name
                            break
            if not target_id:
                r = await message.reply_text(
                    f"⚠️ لم أجد المستخدم «{parts[1]}».\n"
                    "تأكد من اليوزر أو استخدم الرد المباشر."
                )
                asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
                return

    if not target_id:
        r = await message.reply_text(
            "🤫 <b>كيفية الهمسة:</b>\n\n"
            "• <b>ارد</b> على رسالة الشخص واكتب <b>همسة</b>\n"
            "• أو: <b>همسة @يوزر</b>\n\n"
            "مثال: <code>همسة @ahmed</code>",
            parse_mode=ParseMode.HTML
        )
        asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
        return

    if target_id == user_id:
        r = await message.reply_text("😅 لا يمكنك الهمس لنفسك!")
        asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
        return

    pending_id = str(uuid.uuid4())[:8]
    WHISPERS_CACHE[f"pending|{pending_id}"] = {
        'group_id':  group_id,
        'from_id':   user_id,
        'from_name': fname,
        'to_id':     target_id,
        'to_name':   target_name,
    }
    target_mention = f'<a href="tg://user?id={target_id}">{target_name}</a>'
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🤫 اهمس هنا",
            switch_inline_query_current_chat=f"whs {pending_id} "
        )
    ]])
    await message.reply_text(
        f"• تم تحديد الهمسة لـ {target_mention} ←\n"
        f"• اضغط الزر لكتابة الهمسة",
        parse_mode=ParseMode.HTML,
        reply_markup=kb
    )

    async def _expire_pending():
        await asyncio.sleep(300)
        WHISPERS_CACHE.pop(f"pending|{pending_id}", None)
    asyncio.create_task(_expire_pending())


# ==================== قوائم الأوامر ====================

_back_btn = [[InlineKeyboardButton("🔙 رجوع", callback_data='commands_menu')]]


async def show_main_menu(client, cq: CallbackQuery):
    await cq.message.edit_text(
        "أهلاً بك في بوت ذكي المجاني! 🤖\n\n"
        "🧠 ذكاء اصطناعي · 🎮 ألعاب · 💰 عملات · ⚡ تفاعل\n\n"
        "اختر من القائمة أدناه:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "➕ أضفني إلى مجموعتك",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=start"
            )],
            [InlineKeyboardButton("📜 الأوامر", callback_data='commands_menu')],
        ])
    )


async def show_commands_menu(client, cq: CallbackQuery):
    await cq.message.edit_text(
        "📋 <b>قائمة الأوامر</b>\n\nاختر القسم الذي تريده:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⚙️ أوامر الإدارة",   callback_data='admin_tab'),
             InlineKeyboardButton("👤 أوامر الأعضاء",  callback_data='user_tab')],
            [InlineKeyboardButton("🎮 التسلية والألعاب", callback_data='games_tab'),
             InlineKeyboardButton("📊 الإحصائيات",      callback_data='stats_tab')],
            [InlineKeyboardButton("🤖 أوامر الذكاء الاصطناعي", callback_data='ai_tab')],
            [InlineKeyboardButton("🔙 رجوع",             callback_data='main_menu')],
        ])
    )


async def show_admin_menu(client, cq: CallbackQuery):
    await cq.message.edit_text(
        "⚙️ <b>أوامر الإدارة</b>\n"
        "<i>كل أمر يعمل بالرد المباشر أو @يوزر</i>\n\n"
        "━━━━━━ 🔇 العقوبات ━━━━━━\n"
        "• <b>كتم</b> — كتم دائم\n"
        "• <b>كتم 30</b> — كتم مؤقت (بالدقائق)\n"
        "• <b>الغاء الكتم</b> — رفع الكتم\n"
        "• <b>تحذير</b> — تحذير (3 تحذيرات = كتم تلقائي)\n"
        "• <b>مسح التحذيرات</b> — مسح تحذيرات عضو\n"
        "• <b>عقوبات</b> — سجل عقوبات عضو\n"
        "• <b>حظر</b> — حظر نهائي\n"
        "• <b>طرد</b> — طرد من المجموعة\n"
        "• <b>مسح 10</b> — حذف آخر N رسالة\n\n"
        "━━━━━━ 🎖️ الرتب ━━━━━━\n"
        "• م مميز │ اد ادمن │ مد مدير\n"
        "• من منشئ │ مط مطور │ تك تنزيل\n\n"
        "━━━━━━ 🔒 الأقفال (قفل/فتح) ━━━━━━\n"
        "الفشار │ الروابط │ المعرفات\n"
        "الكلايش │ التوجيه │ الاجنبي │ التكرار\n\n"
        "━━━━━━ 🐢 الوضع البطيء ━━━━━━\n"
        "• <b>بطيء 30</b> — تأخير 30 ثانية بين رسائل الأعضاء\n"
        "• <b>بطيء 0</b> أو <b>فتح البطيء</b> — تعطيل الوضع البطيء\n\n"
        "━━━━━━ ⚙️ إعدادات ━━━━━━\n"
        "• <b>تفع</b> / <b>تعط</b> — تفعيل/تعطيل صور البروفايل\n"
        "• <b>المكتومين</b> — عرض قائمة المكتومين\n"
        "• <b>مسح المكتومين</b> — رفع الكتم عن الجميع\n"
        "• <b>احصاء</b> — إحصائيات المجموعة\n\n"
        "━━━━━━ 🤫 الهمسة ━━━━━━\n"
        "• <b>تفعيل الهمسة</b> — تشغيل ميزة الهمسة\n"
        "• <b>تعطيل الهمسة</b> — إيقاف ميزة الهمسة\n\n"
        "━━━━━━ 🗑️ الحذف التلقائي للميديا ━━━━━━\n"
        "• <b>تفع حذف</b> — تفعيل حذف الميديا تلقائياً\n"
        "• <b>تعط حذف</b> — تعطيل حذف الميديا\n"
        "📌 <i>يحذف الصور والمقاطع والملصقات والمتحركات بعد 5 دقائق</i>\n"
        "🔒 <i>رسائل المثبتات محمية من الحذف</i>\n\n"
        "━━━━━━ 📢 التاك التلقائي ━━━━━━\n"
        "• <b>تاك تلقائي</b> — إرسال كليشة لعدد محدد من الأعضاء\n"
        "  ① اكتب نص الكليشة\n"
        "  ② اكتب عدد الأشخاص (حتى 200)\n"
        "  ✅ تُرسل الكليشة وتُذكَر الأعضاء تلقائياً\n"
        "🔒 <i>متاح للمشرفين فقط</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(_back_btn)
    )


async def show_user_menu(client, cq: CallbackQuery):
    await cq.message.edit_text(
        "👤 <b>أوامر الأعضاء</b>\n\n"
        "━━━━━━ 🪪 معلوماتي ━━━━━━\n"
        "• <b>ا</b> — البروفايل الشخصي\n"
        "• <b>بايو</b> — نبذتك الشخصية\n"
        "• <b>ر</b> — رتبتك في المجموعة\n"
        "• <b>ن</b> — رصيد عملاتك\n"
        "• <b>عقوباتي</b> — سجل عقوباتك\n\n"
        "━━━━━━ 🏆 تنافسي ━━━━━━\n"
        "• <b>ت</b> — لوحة المتصدرين\n"
        "• <b>احصاء</b> — إحصائيات المجموعة",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(_back_btn)
    )


async def show_games_menu(client, cq: CallbackQuery):
    await cq.message.edit_text(
        "🎮 <b>التسلية والألعاب</b>\n\n"
        "━━━━━━ 🎯 كويز تفاعلي ━━━━━━\n"
        "• <b>لغز</b> — سؤال بـ 4 خيارات | كل إجابة صحيحة = 💰 عملة + 5 XP\n\n"
        "━━━━━━ 🎰 الكازينو ━━━━━━\n"
        "• <b>كازينو 2</b> — ماكينة حقيقية | جاكبوت = ×5 | ثلاثية = ×3\n\n"
        "━━━━━━ ⚔️ تحدي النرد PvP ━━━━━━\n"
        "• <b>تحدي 2</b> — تحدّ منافساً بنرد حقيقي!\n\n"
        "━━━━━━ 🏀 تحدي الكرة ━━━━━━\n"
        "• <b>كرة 2</b> — رهان على رمية كرة حقيقية!\n\n"
        "━━━━━━ ⚡ سباق الكتابة ━━━━━━\n"
        "• <b>سباق</b> — أول من يكتب الجملة = 3 عملات!\n\n"
        "━━━━━━ 🔗 الوصلة الجماعية ━━━━━━\n"
        "• <b>وصلة</b> — كل 5 كلمات صحيحة = 💰 عملة!\n\n"
        "━━━━━━ 📖 أكمل المثل ━━━━━━\n"
        "• <b>مثل</b> — أول مجيب = عملة | زر 💡 للمساعدة\n\n"
        "━━━━━━ ❌⭕ لعبة XO ━━━━━━\n"
        "• <b>xo</b> أو <b>xo @يوزر</b> — تحدي أو لعب مع الذكاء الاصطناعي\n\n"
        "━━━━━━ 💡 طريقة الربح ━━━━━━\n"
        "100 رسالة = عملة ✦ الألعاب = عملات وـ XP",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(_back_btn)
    )


async def show_stats_menu(client, cq: CallbackQuery):
    await cq.message.edit_text(
        "📊 <b>الإحصائيات</b>\n\n"
        "• <b>احصاء</b> — إحصائيات المجموعة\n"
        "• <b>ت</b> — لوحة المتصدرين بالنقاط",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(_back_btn)
    )


async def show_ai_menu(client, cq: CallbackQuery):
    chat_id = cq.message.chat.id
    state = await _get_alert_state(chat_id)
    status = "🟢 مفعّل" if state["active"] else "🔴 غير مفعّل"
    minutes = state.get("minutes", 0)
    duration_text = f"({minutes} دقيقة)" if state["active"] and minutes else ""
    await cq.message.edit_text(
        f"🤖 <b>أوامر الذكاء الاصطناعي</b>\n\n"
        f"━━━━━━ 🛡️ وضع التأهب ━━━━━━\n"
        f"الحالة: {status} {duration_text}\n\n"
        f"عند تفعيله يقفل البوت تلقائياً:\n"
        f"• الروابط والمعرفات\n"
        f"• الوسائط بأنواعها\n"
        f"• التوجيه والفشار والتكرار\n\n"
        f"<i>يُفعَّل عند غياب المشرفين للمدة المحددة</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛡️ تفعيل وضع التأهب", callback_data='alert_setup')],
            [InlineKeyboardButton("❌ إيقاف التأهب",      callback_data='alert_off')],
            [InlineKeyboardButton("🔙 رجوع",               callback_data='commands_menu')],
        ])
    )


async def show_alert_setup(client, cq: CallbackQuery):
    await cq.message.edit_text(
        "⏱️ <b>اختر مدة الغياب لتفعيل الحماية:</b>\n\n"
        "إذا لم يُرسل أي مشرف أو مدير رسالة خلال المدة المحددة،\n"
        "سيُفعَّل وضع الحماية الكامل تلقائياً.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏱ ربع ساعة",    callback_data='alert_set|15'),
             InlineKeyboardButton("⏱ نصف ساعة",    callback_data='alert_set|30')],
            [InlineKeyboardButton("⏱ ساعة",         callback_data='alert_set|60'),
             InlineKeyboardButton("⏱ ساعة ونصف",   callback_data='alert_set|90')],
            [InlineKeyboardButton("⏱ ساعتين",       callback_data='alert_set|120')],
            [InlineKeyboardButton("🔙 رجوع",         callback_data='ai_tab')],
        ])
    )


# ==================== معالج الأزرار ====================

@app.on_callback_query()
async def button_handler(client: Client, cq: CallbackQuery):
    data = cq.data or ""

    if data.startswith("whs|"):
        whisper_id = data.split("|")[1]
        whisper    = WHISPERS_CACHE.get(whisper_id)
        if not whisper:
            await cq.answer("⚠️ هذه الهمسة قديمة ومسحت من الذاكرة.", show_alert=True)
            return
        if cq.from_user.id in (whisper['to_id'], whisper['from_id']):
            await cq.answer(f"الهمسة:\n\n{whisper['text']}", show_alert=True)
        else:
            await cq.answer("👀 عذراً، هذه الهمسة ليست لك، يا فضولي!", show_alert=True)
        return

    if data.startswith("qz|"):
        parts = data.split("|")
        await game_quiz_callback(client, cq, int(parts[1]), int(parts[2]))
        return

    if data.startswith("duel|"):
        parts  = data.split("|")
        action = parts[1]
        gid    = int(parts[2])
        if action == "join":   await game_duel_join(client, cq, gid)
        elif action == "cancel": await game_duel_cancel(client, cq, gid)
        return

    if data.startswith("hint|"):
        await game_mathal_hint(client, cq, int(data.split("|")[1]))
        return

    if data.startswith("xo_accept|"):
        await _xo_accept_challenge(client, cq, int(data.split("|")[2]))
        return

    if data.startswith("xo_accept_any|"):
        await _xo_accept_any(client, cq, int(data.split("|")[1]))
        return

    if data.startswith("xo_bot|"):
        await _xo_start_bot(client, cq, int(data.split("|")[1]))
        return

    if data.startswith("xo_play|"):
        await _xo_play(client, cq, int(data.split("|")[1]))
        return

    if data == "xo_surrender":
        await _xo_surrender(client, cq); return

    if data == "xo_decline":
        await cq.answer("تم الرفض.")
        try: await cq.message.edit_text("❌ تم رفض التحدي.")
        except: pass
        return

    if data == "xo_restart":
        await _xo_restart(client, cq); return

    if data == "xo_done":
        await cq.answer(); return

    if data.startswith("waslah|end|"):
        gid = int(data.split("|")[2])
        g   = group_games.get(gid, {})
        if g.get('waslah', {}).get('active'):
            total = len(g['waslah'].get('used', set())) - 1
            g['waslah'] = {}
            await cq.answer(f"انتهت الوصلة! مجموع الكلمات: {total} 🔗", show_alert=True)
            try: await cq.message.edit_reply_markup(None)
            except: pass
        else:
            await cq.answer("لا توجد وصلة نشطة.", show_alert=True)
        return

    # -------- زر "بدون نص" عند إضافة الردود المخصصة --------
    if data.startswith("no_text_reply|"):
        admin_id = int(data.split("|")[1])
        if cq.from_user.id != admin_id:
            await cq.answer("هذا الزر ليس لك!", show_alert=True)
            return
        pending = pending_replies.get(admin_id)
        if not pending or pending.get('stage') != 3:
            await cq.answer("انتهت الجلسة أو لا توجد جلسة نشطة.", show_alert=True)
            return
        db_add_reply(
            pending['target_user_id'],
            pending['trigger_name'],
            "",
            pending['target_tg_username'],
        )
        pending_replies.pop(admin_id, None)
        await cq.answer("✅ تم الحفظ بدون نص")
        try:
            await cq.message.edit_text(
                f"✅ <b>تم حفظ الرد بنجاح!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"👤 الشخص: {pending['target_display']}\n"
                f"🔑 الاسم المُشغِّل: <b>{pending['trigger_name']}</b>\n"
                f"💬 النص: بدون نص",
                parse_mode=ParseMode.HTML
            )
        except: pass
        return

    # -------- زر إلغاء إضافة الردود المخصصة --------
    if data.startswith("cancel_reply|"):
        admin_id = int(data.split("|")[1])
        if cq.from_user.id != admin_id:
            await cq.answer("هذا الزر ليس لك!", show_alert=True)
            return
        if admin_id in pending_replies:
            pending_replies.pop(admin_id, None)
        await cq.answer("تم إلغاء الأمر")
        try:
            await cq.message.edit_text("❌ تم إلغاء الأمر.")
        except:
            pass
        return

    # -------- زر إلغاء حذف الردود المخصصة --------
    if data.startswith("cancel_del_reply|"):
        admin_id = int(data.split("|")[1])
        if cq.from_user.id != admin_id:
            await cq.answer("هذا الزر ليس لك!", show_alert=True)
            return
        if admin_id in pending_delete_replies:
            pending_delete_replies.pop(admin_id, None)
        await cq.answer("تم إلغاء الأمر")
        try:
            await cq.message.edit_text("❌ تم إلغاء أمر الحذف.")
        except:
            pass
        return

    # -------- زر إلغاء التاك التلقائي --------
    if data.startswith("cancel_auto_tag|"):
        admin_id = int(data.split("|")[1])
        if cq.from_user.id != admin_id:
            await cq.answer("هذا الزر ليس لك!", show_alert=True)
            return
        pending_auto_tag.pop(admin_id, None)
        await cq.answer("تم إلغاء التاك التلقائي")
        try:
            await cq.message.edit_text("❌ تم إلغاء التاك التلقائي.")
        except:
            pass
        return

    await cq.answer()
    menus = {
        'admin_tab': show_admin_menu, 'user_tab':  show_user_menu,
        'games_tab': show_games_menu, 'stats_tab': show_stats_menu,
    }
    if data == 'commands_menu':   await show_commands_menu(client, cq)
    elif data in menus:           await menus[data](client, cq)
    elif data == 'main_menu':     await show_main_menu(client, cq)
    elif data == 'ai_tab':        await show_ai_menu(client, cq)
    elif data == 'alert_setup':
        if not await is_admin(client, cq.message.chat.id, cq.from_user.id):
            await cq.answer("⛔ هذا الأمر للمشرفين فقط!", show_alert=True); return
        await show_alert_setup(client, cq)
    elif data.startswith('alert_set|'):
        if not await is_admin(client, cq.message.chat.id, cq.from_user.id):
            await cq.answer("⛔ هذا الأمر للمشرفين فقط!", show_alert=True); return
        minutes = int(data.split('|')[1])
        chat_id = cq.message.chat.id
        state = await _get_alert_state(chat_id)
        # إلغاء المهمة القديمة
        if state.get("task") and not state["task"].done():
            state["task"].cancel()
        state["active"]  = True
        state["minutes"] = minutes
        state["last_admin_msg"] = datetime.now(timezone.utc)
        state["task"] = asyncio.get_event_loop().create_task(
            _alert_watcher(client, chat_id, minutes)
        )
        labels = {15:"ربع ساعة", 30:"نصف ساعة", 60:"ساعة", 90:"ساعة ونصف", 120:"ساعتين"}
        label = labels.get(minutes, f"{minutes} دقيقة")
        await cq.answer(f"✅ وضع التأهب مفعّل — {label}", show_alert=True)
        await show_ai_menu(client, cq)
    elif data == 'alert_off':
        if not await is_admin(client, cq.message.chat.id, cq.from_user.id):
            await cq.answer("⛔ هذا الأمر للمشرفين فقط!", show_alert=True); return
        chat_id = cq.message.chat.id
        state = await _get_alert_state(chat_id)
        if state.get("task") and not state["task"].done():
            state["task"].cancel()
        state["active"]  = False
        state["minutes"] = 0
        state["task"]    = None
        await _deactivate_full_protection(client, chat_id)
        await cq.answer("✅ تم إيقاف وضع التأهب ورفع الحماية", show_alert=True)
        await show_ai_menu(client, cq)


# ==================== معالج Inline (الهمسة) ====================

@app.on_inline_query()
async def inline_whisper_handler(client: Client, inline_query: InlineQuery):
    query = inline_query.query.strip()
    if not query.startswith("whs "):
        return
    parts        = query.split(" ", 2)
    if len(parts) < 2:
        return
    pending_id   = parts[1]
    whisper_text = parts[2].strip() if len(parts) > 2 else ""
    pending      = WHISPERS_CACHE.get(f"pending|{pending_id}")

    if not pending:
        await inline_query.answer(
            results=[InlineQueryResultArticle(
                title="⚠️ انتهت صلاحية الهمسة",
                input_message_content=InputTextMessageContent("_"),
                description="ابدأ من جديد بكتابة همسة"
            )],
            cache_time=1
        )
        return

    target_name = pending['to_name']
    if not whisper_text:
        await inline_query.answer(
            results=[InlineQueryResultArticle(
                title=f"✍️ اكتب همستك لـ {target_name}",
                input_message_content=InputTextMessageContent("_"),
                description="اكتب نص الهمسة بعد المسافة..."
            )],
            cache_time=1
        )
        return

    import uuid as _uuid
    whisper_id  = str(_uuid.uuid4())[:8]
    from_id     = pending['from_id']
    from_name   = pending['from_name']
    to_id       = pending['to_id']
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("👁 رؤية الهمسة", callback_data=f"whs|{whisper_id}")
    ]])
    result_text = (
        f"• الهمسة لـ <a href='tg://user?id={to_id}'>{target_name}</a> ←\n"
        f"• من <a href='tg://user?id={from_id}'>{from_name}</a> ←\n"
        f"-"
    )
    await inline_query.answer(
        results=[InlineQueryResultArticle(
            title=f"🤫 إرسال همسة لـ {target_name}",
            input_message_content=InputTextMessageContent(
                result_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True
            ),
            description=f"الهمسة: {whisper_text[:40]}{'...' if len(whisper_text) > 40 else ''}",
            reply_markup=kb
        )],
        cache_time=1, is_personal=True
    )
    WHISPERS_CACHE[whisper_id] = {'from_id': from_id, 'to_id': to_id, 'text': whisper_text}


# ==================== الترحيب ====================

@app.on_message(filters.new_chat_members & filters.group)
async def welcome_new_member(client: Client, message: Message):
    for m in message.new_chat_members:
        if m.is_bot:
            continue
        mention = f"@{m.username}" if m.username else m.first_name
        await message.reply_text(random.choice(WELCOME_MESSAGES).format(mention=mention))


# ==================== /start وSlash Commands ====================

@app.on_message(filters.command("start"))
async def start(client: Client, message: Message):
    if message.chat.type == ChatType.PRIVATE:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "➕ أضفني إلى مجموعتك",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=start"
            )
        ]])
        await message.reply_text(
            "أهلاً بك في بوت ذكي المجاني! 🤖\n\n"
            "🧠 ذكاء اصطناعي · 🎮 ألعاب · 💰 عملات · ⚡ تفاعل\n\n"
            "أضفني إلى مجموعتك واستمتع بجميع الميزات!",
            reply_markup=kb
        )
    else:
        await message.reply_text(
            "✅ البوت يعمل بنجاح في هذه المجموعة.\n"
            "اكتب <b>اوامر</b> لاستعراض الأوامر المتاحة.",
            parse_mode=ParseMode.HTML
        )


async def _private_only_reply(message: Message, feature: str = "هذا الأمر"):
    await message.reply_text(
        f"🚫 {feature} مخصص للمجموعات فقط.\n"
        "أضفني إلى مجموعتك واستمتع بجميع الميزات!"
    )


@app.on_message(filters.command(["id", "myid", "profile"]))
async def slash_id(client: Client, message: Message):
    if message.chat.type == ChatType.PRIVATE:
        await _private_only_reply(message, "عرض البروفايل"); return
    await cmd_profile(client, message)


@app.on_message(filters.command(["bio", "bayo"]))
async def slash_bio(client: Client, message: Message):
    if message.chat.type == ChatType.PRIVATE:
        await _private_only_reply(message, "عرض النبذة"); return
    await cmd_bio(client, message)


@app.on_message(filters.command(["xo"]))
async def slash_xo(client: Client, message: Message):
    from games import game_xo_start
    if message.chat.type == ChatType.PRIVATE:
        await _private_only_reply(message, "لعبة XO"); return
    await game_xo_start(client, message)


@app.on_message(filters.command(["لغز", "quiz"]))
async def slash_quiz(client: Client, message: Message):
    from games import game_quiz_start
    if message.chat.type == ChatType.PRIVATE:
        await _private_only_reply(message, "الكويز"); return
    await game_quiz_start(client, message)


@app.on_message(filters.command(["مثل", "mathal"]))
async def slash_mathal(client: Client, message: Message):
    from games import game_mathal_start
    if message.chat.type == ChatType.PRIVATE:
        await _private_only_reply(message, "أكمل المثل"); return
    await game_mathal_start(client, message)


@app.on_message(filters.command(["سباق", "race"]))
async def slash_race(client: Client, message: Message):
    from games import game_race_start
    if message.chat.type == ChatType.PRIVATE:
        await _private_only_reply(message, "سباق الكتابة"); return
    await game_race_start(client, message)


@app.on_message(filters.command(["وصلة", "waslah"]))
async def slash_waslah(client: Client, message: Message):
    from games import game_waslah_start
    if message.chat.type == ChatType.PRIVATE:
        await _private_only_reply(message, "الوصلة"); return
    await game_waslah_start(client, message)


@app.on_message(filters.command(["اوامر", "commands", "help"]))
async def slash_commands(client: Client, message: Message):
    if message.chat.type == ChatType.PRIVATE:
        await _private_only_reply(message, "قائمة الأوامر"); return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ أوامر الإدارة",   callback_data='admin_tab'),
         InlineKeyboardButton("👤 أوامر الأعضاء",  callback_data='user_tab')],
        [InlineKeyboardButton("🎮 التسلية والألعاب", callback_data='games_tab'),
         InlineKeyboardButton("📊 الإحصائيات",      callback_data='stats_tab')],
        [InlineKeyboardButton("🤖 أوامر الذكاء الاصطناعي", callback_data='ai_tab')],
    ])
    await message.reply_text(
        "📋 <b>قائمة الأوامر</b>\n\nاختر القسم الذي تريده:",
        parse_mode=ParseMode.HTML, reply_markup=kb
    )


# ══════════════════ HANDLERS MESSAGES ══════════════════

_auto_delete_batches: dict = {}
_active_delete_tasks: set  = set()

# ==================== قائمة جمل النداء ====================
NDA_MESSAGES = [
    # غزل
    "🌹 يا زين، وجودك ينور المكان ويضيف للمجموعة جمالاً ما ينوصف.",
    "💫 لو الجمال وردة، أنت تاج الوردة.",
    "✨ عيونك نجوم تضيء ليالي المجموعة.",
    "🌸 وجودك مثل نسيم الربيع، يجي ويخلي الجو أحلى.",
    "💖 يا غالي، كلامك دائماً يسعد القلب.",
    "🌙 يا قمر، نورت المجموعة بنورك.",
    "🦋 أنت فراشة المجموعة، كل ما طرت زاد الجمال.",
    "💎 أغلى من الألماس وأجمل من القمر.",
    "🌺 يا ورد، عطرك فاح وملىء المكان.",
    "🔥 وجودك نار، وكلامك شرارة.",
    # حكم
    "📖 اضحك يضحك العالم معك، ابكِ وتبكِ وحدك.",
    "🌟 من صبر ظفر، ومن جدّ وجد.",
    "🕊 الطير اللي يطير عالي، ما ينسى عشه.",
    "💡 العقل زينة، والأدب زيادة.",
    "🌊 كلّ وعاء يرشح بما فيه.",
    "🎯 خذ القرار ولا تحتار.",
    "🌱 من يزرع الشوك، لا يحصد العنب.",
    "⏰ الوقت كالسيف إن لم تقطعه قطعك.",
    "📚 اطلب العلم من المهد إلى اللحد.",
    "🤝 الصديق وقت الضيق.",
    # جبر خواطر
    "💪 أنت أقوى مما تظن، وقدرك أكبر مما تتخيل.",
    "🌈 بعد كل ليلة ظلام، يطلع فجر جديد.",
    "❤️ قلبك الطيب هو أجمل ما فيك، لا تغيّره.",
    "🌻 ابتسم، فأنت جميل حين تبتسم.",
    "🦅 العقبة ما تجي إلا للي عنده جناح.",
    "💫 ربما تأخّرت أحلامك، لكنها ما راحت.",
    "🌊 موج البحر يعلّمك: مهما ارتفع، يرجع ويرتفع ثاني.",
    "🌟 أنت نجم، بس الغيمة اللي قدامك تخفي ضوّك.",
    "🍃 ارتاح، ربك ما نساك ولا تركك.",
    "🔥 جمرك ما طفى، بس محتاج نفخة أمل.",
]


async def _fire_custom_reply(message: Message, client: Client,
                             uid: int, display: str,
                             rtext: str, media_type: str, media_file_id: str):
    """يُرسل الرد المخصص (نص / صورة / فيديو / انيميشن) مع ذكر الشخص المستهدف."""
    mention = f'<a href="tg://user?id={uid}">{display}</a>'
    caption = mention + (f"\n\n{rtext}" if rtext else "")

    if media_type == "photo" and media_file_id:
        await message.reply_photo(media_file_id, caption=caption, parse_mode=ParseMode.HTML)
    elif media_type == "video" and media_file_id:
        await message.reply_video(media_file_id, caption=caption, parse_mode=ParseMode.HTML)
    elif media_type == "animation" and media_file_id:
        await message.reply_animation(media_file_id, caption=caption, parse_mode=ParseMode.HTML)
    else:
        await message.reply_text(caption, parse_mode=ParseMode.HTML)


# ══════════════════════════════════════════════════════════
#  ميزة يوت — v3 (2026) — مقاومة لحماية يوتيوب الجديدة
#  التحسينات:
#    1. تجريب عدة player_clients بترتيب الأنجح في 2026:
#         tv_simply → ios → web_safari → mweb → tv → android
#       (الأولى لا تحتاج PO Token عادةً)
#    2. format بسيط ومرن: bestaudio/best بدون قيود صارمة
#    3. format_sort بصيغة yt-dlp الصحيحة: aext:m4a (مو acodec:m4a)
#    4. retry تلقائي بأكثر من client عند فشل أحدها
#    5. رسائل خطأ واضحة بالعراقي للمستخدم
#    6. دعم تلقائي لـ cookies.txt إن وُجد (يتجاوز bot detection)
# ══════════════════════════════════════════════════════════

import shutil as _shutil
import sys as _sys
import os as _os

# ── كاش لمسار ffmpeg (يحسب مرة واحدة عند تحميل الموديول) ──
_FFMPEG_PATH = _shutil.which("ffmpeg")
_HAS_FFMPEG  = _FFMPEG_PATH is not None

# ── قائمة player_clients بترتيب الأنجح في 2026 ──
# tv_simply: لا يحتاج PO Token، يعطي صيغ صوت m4a/opus
# ios:       يعمل غالباً بدون PO Token، يعطي m4a 128kbps
# web_safari: متصفح Safari — يتجاوز كثير من الفحوصات
# mweb:      موبايل ويب — احتياط
# tv:        تلفزيون كامل — احتياط
# android:   آخر ملاذ
_YT_CLIENT_ORDER = ["tv_simply", "ios", "web_safari", "mweb", "tv", "android"]


def _get_ffmpeg_path():
    """التحقق من وجود ffmpeg — استخدم القيمة المخزّنة."""
    return _FFMPEG_PATH


def _get_cookies_path():
    """البحث عن ملف cookies.txt في مسارات شائعة."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt"),
        os.path.expanduser("~/cookies.txt"),
        "/root/cookies.txt",
        "/app/cookies.txt",
        "/home/container/cookies.txt",
    ]
    for p in candidates:
        if os.path.isfile(p) and os.path.getsize(p) > 100:
            return p
    return None


def _build_ydl_opts(out_dir: str, full_mode: bool, clients: list):
    """
    يبني خيارات yt-dlp مع قائمة player_clients محددة.
    - format = bestaudio/best (مرن، يقبل أي صيغة).
    - format_sort = aext:m4a (الصحيح بـ yt-dlp بدل acodec:m4a الخطأ).
    """
    if full_mode:
        max_duration = 1500   # 25 دقيقة
        max_filesize = 45 * 1024 * 1024
    else:
        max_duration = 600    # 10 دقائق
        max_filesize = 18 * 1024 * 1024

    opts = {
        "format":                     "bestaudio/best",
        # ✅ الصيغة الصحيحة: aext (audio extension) مو acodec
        "format_sort":                ["aext:m4a", "aext:webm", "abr~128"],
        "outtmpl":                    os.path.join(out_dir, "%(id)s.%(ext)s"),
        "noplaylist":                 True,
        "quiet":                      True,
        "no_warnings":                True,
        "noprogress":                 True,
        "socket_timeout":             10,
        "retries":                    2,
        "extractor_retries":          2,
        "fragment_retries":           3,
        "skip_unavailable_fragments": True,
        "concurrent_fragments":       4,
        "http_chunk_size":            1024 * 1024,
        "max_filesize":               max_filesize,
        "geo_bypass":                 True,
        "nocheckcertificate":         True,
        "extractor_args": {
            "youtube": {
                "player_client": clients,
                # تجاوز فحوصات إضافية
                "player_skip":   ["webpage", "configs"],
            }
        },
    }
    # match_filter اختياري — لا نطبّقه على البحث، فقط على التحميل
    if max_duration:
        try:
            import yt_dlp
            opts["match_filter"] = yt_dlp.utils.match_filter_func(
                f"duration < {max_duration}"
            )
        except Exception:
            pass

    _cookies = _get_cookies_path()
    if _cookies:
        opts["cookiefile"] = _cookies
    return opts


def _yt_search_id(query: str):
    """
    يبحث عن أول فيديو مطابق ويرجع (video_id, title).
    يجرّب عدة clients بالترتيب — أول واحد ينجح يستخدمه.
    """
    try:
        import yt_dlp
    except ImportError:
        logging.error("[yt-search] yt-dlp غير مثبّت")
        return None

    last_err = None
    # نجرّب client واحد كل مرة للسرعة في البحث
    for client_name in _YT_CLIENT_ORDER[:4]:
        ydl_opts = {
            "quiet":              True,
            "no_warnings":        True,
            "extract_flat":       True,
            "skip_download":      True,
            "noplaylist":         True,
            "socket_timeout":     8,
            "retries":            1,
            "extractor_retries":  1,
            "geo_bypass":         True,
            "nocheckcertificate": True,
            "extractor_args": {
                "youtube": {"player_client": [client_name]}
            },
        }
        _cookies = _get_cookies_path()
        if _cookies:
            ydl_opts["cookiefile"] = _cookies

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch3:{query}", download=False)
            if not info:
                continue
            entries = info.get("entries") or []
            for entry in entries:
                if not entry:
                    continue
                vid   = entry.get("id") or entry.get("videoId")
                title = entry.get("title") or query
                if not vid or len(vid) != 11:
                    continue
                ie_key = entry.get("ie_key", "") or entry.get("_type", "")
                if ie_key in ("YoutubeTab", "YoutubePlaylist"):
                    continue
                if entry.get("channel_id") == vid:
                    continue
                logging.info(f"[yt-search] نجح بـ client={client_name} → {vid}")
                return vid, title
        except Exception as e:
            last_err = str(e)
            logging.warning(f"[yt-search] فشل client={client_name}: {e}")
            continue

    if last_err:
        logging.error(f"[yt-search] فشل جميع الـ clients. آخر خطأ: {last_err}")
    return None


def _yt_download_by_id(video_id: str, title: str, out_dir: str, full_mode: bool = False):
    """
    يحمّل فيديو معروف الـ id. يجرّب عدة player_clients بالتتابع
    حتى ينجح أحدها — وهي الطريقة الأنجع لتجاوز bot detection.
    يرجع (file_path, title) أو None أو ("TOO_LARGE", title).
    """
    try:
        import yt_dlp
    except ImportError:
        logging.error("[yt-download] yt-dlp غير مثبّت")
        return None

    url = f"https://www.youtube.com/watch?v={video_id}"

    last_err = None
    bot_detected = False
    too_large = False

    # نجرّب كل client على حدة — بعضها يفشل والبعض ينجح
    for client_name in _YT_CLIENT_ORDER:
        # نظّف المجلد قبل المحاولة الجديدة
        for fname in list(os.listdir(out_dir)):
            try:
                os.remove(os.path.join(out_dir, fname))
            except Exception:
                pass

        ydl_opts = _build_ydl_opts(out_dir, full_mode, [client_name])

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # تحقق من الملف الناتج
            candidates = []
            for fname in os.listdir(out_dir):
                fp = os.path.join(out_dir, fname)
                if os.path.isfile(fp) and os.path.getsize(fp) > 5000:
                    if fname.endswith(('.m4a', '.mp3', '.ogg', '.webm',
                                       '.mp4', '.opus', '.aac')):
                        candidates.append((fp, os.path.getsize(fp)))

            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                logging.info(f"[yt-download] نجح بـ client={client_name}")
                return candidates[0][0], title

        except yt_dlp.utils.DownloadError as e:
            err_str = str(e).lower()
            last_err = str(e)
            if "file is larger than max-filesize" in err_str or "max_filesize" in err_str:
                too_large = True
                logging.warning(f"[yt-download] الملف أكبر من الحد")
                break  # ما فائدة من تجريب clients ثانية
            if any(k in err_str for k in [
                "sign in to confirm", "not a bot", "bot",
                "please sign in", "po token", "po_token"
            ]):
                bot_detected = True
                logging.warning(f"[yt-download] bot detection مع client={client_name}")
            else:
                logging.warning(f"[yt-download] فشل client={client_name}: {e}")
            continue
        except Exception as e:
            last_err = str(e)
            logging.warning(f"[yt-download] استثناء client={client_name}: {e}")
            continue

    if too_large:
        return ("TOO_LARGE", title)

    if bot_detected:
        return ("BOT_DETECTED", title)

    logging.error(f"[yt-download] فشل جميع الـ clients. آخر خطأ: {last_err}")
    return None


def _yt_search_and_download(query: str, out_dir: str, full_mode: bool = False):
    """
    fallback شامل: يبحث ويحمّل في خطوة واحدة، يجرّب عدة clients.
    يستخدم لو _yt_search_id فشل.
    """
    try:
        import yt_dlp
    except ImportError:
        return None

    last_err = None
    bot_detected = False
    too_large = False

    for client_name in _YT_CLIENT_ORDER:
        # نظّف المجلد
        for fname in list(os.listdir(out_dir)):
            try:
                os.remove(os.path.join(out_dir, fname))
            except Exception:
                pass

        ydl_opts = _build_ydl_opts(out_dir, full_mode, [client_name])
        title    = query

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            if info:
                entry = (info.get("entries") or [info])[0]
                title = (entry or {}).get("title") or query

            candidates = []
            for fname in os.listdir(out_dir):
                fp = os.path.join(out_dir, fname)
                if os.path.isfile(fp) and os.path.getsize(fp) > 5000:
                    if fname.endswith(('.m4a', '.mp3', '.ogg', '.webm',
                                       '.mp4', '.opus', '.aac')):
                        candidates.append((fp, os.path.getsize(fp)))

            if candidates:
                candidates.sort(key=lambda x: x[1], reverse=True)
                logging.info(f"[yt-search-dl] نجح بـ client={client_name}")
                return candidates[0][0], title

        except yt_dlp.utils.DownloadError as e:
            err_str = str(e).lower()
            last_err = str(e)
            if "file is larger than max-filesize" in err_str:
                too_large = True
                break
            if any(k in err_str for k in [
                "sign in to confirm", "not a bot", "bot",
                "please sign in", "po token", "po_token"
            ]):
                bot_detected = True
            continue
        except Exception as e:
            last_err = str(e)
            continue

    if too_large:
        return ("TOO_LARGE", query)
    if bot_detected:
        return ("BOT_DETECTED", query)

    logging.error(f"[yt-search-dl] فشل جميع الـ clients. آخر خطأ: {last_err}")
    return None


@app.on_message(filters.all & filters.group & ~filters.bot, group=-1)
async def _track_admin_activity(client: Client, message: Message):
    """يحدّث وقت آخر رسالة للمشرفين لنظام التأهب"""
    try:
        if not message.from_user:
            return
        user_id = message.from_user.id
        chat_id = message.chat.id
        state = _alert_state.get(chat_id)
        if not state or not state.get("active"):
            return
        if await is_admin(client, chat_id, user_id):
            state["last_admin_msg"] = datetime.now(timezone.utc)
            # إذا كانت الحماية مفعلة، ارفعها
            perms = (await client.get_chat(chat_id)).permissions
            if perms and not perms.can_send_media_messages:
                await _deactivate_full_protection(client, chat_id)
                await client.send_message(
                    chat_id,
                    "🟢 <b>عاد المشرف — تم رفع وضع التأهب</b>",
                    parse_mode=ParseMode.HTML,
                )
    except Exception:
        pass


@app.on_message(filters.text & (filters.group | filters.private) & ~filters.bot)
async def handle_youtube(client: Client, message: Message):
    if not message.from_user:
        return
    text = message.text.strip()
    yt_match = re.match(r"^(يوت|يوتيوب)\s+(.+)$", text, re.IGNORECASE)
    if not yt_match:
        await message.continue_propagation()
        return

    raw_query = yt_match.group(2).strip()
    full_mode  = bool(re.search(r"\s*(كاملة|كامل)\s*$", raw_query))
    query      = re.sub(r"\s*(كاملة|كامل)\s*$", "", raw_query).strip()

    # ── كاش: لو طُلبت قبل → أرسلها فوراً ──
    cached = db_audio_cache_get(query)
    if cached:
        file_id, cached_title = cached
        await message.reply_audio(
            audio      = file_id,
            title      = cached_title[:60],
            performer  = "🎵",
            caption    = f"🎵 <b>{cached_title[:60]}</b>",
            parse_mode = ParseMode.HTML,
        )
        return

    wait_msg = await message.reply_text("🔍 يبحث...")
    tmp_dir  = tempfile.mkdtemp()

    # ── دالة مساعدة: تعديل آمن (يتجاهل MESSAGE_NOT_MODIFIED) ──
    async def _safe_edit(text: str):
        try:
            await wait_msg.edit_text(text)
        except Exception as _e:
            # MESSAGE_NOT_MODIFIED أو أخطاء تعديل أخرى → نتجاهلها
            if "MESSAGE_NOT_MODIFIED" not in str(_e):
                logging.warning(f"[yt-edit] {_e}")

    try:
        loop = asyncio.get_event_loop()

        # ── المسار السريع: search_id ثم download_by_id ──
        # أسرع لأن extract_flat لا يحمّل صفحة الفيديو كاملة
        search_result = await loop.run_in_executor(
            None, _yt_search_id, query
        )

        result = None
        if search_result:
            video_id, title = search_result
            await _safe_edit("⏬ يحمّل...")
            result = await loop.run_in_executor(
                None, _yt_download_by_id, video_id, title, tmp_dir, full_mode
            )

        # ── fallback: لو المسار السريع فشل، استخدم البحث+التحميل المدمج ──
        if not result:
            await _safe_edit("⏬ يحاول مجدداً...")
            result = await loop.run_in_executor(
                None, _yt_search_and_download, query, tmp_dir, full_mode
            )

        if not result:
            await _safe_edit(
                "❌ ما لگيت الأغنية، جرّب اسم ثاني أو كلمات أوضح 🎵"
            )
            return

        if isinstance(result, tuple) and result[0] == "TOO_LARGE":
            title = result[1] if len(result) > 1 else "غير معروف"
            await _safe_edit(
                f"⚠️ الأغنية حجمها كبير، جرّب نسخة أقصر.\n"
                f"🎵 <b>{title[:60]}</b>"
            )
            return

        if isinstance(result, tuple) and result[0] == "BOT_DETECTED":
            # رسالة مفصّلة للمالك، ومختصرة لباقي الناس
            if message.from_user.id == OWNER_ID:
                await _safe_edit(
                    "🤖 <b>يوتيوب طلب تحقّق Bot Detection</b>\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "السبب: يوتيوب صار يحجب طلبات السيرفرات السحابية في 2026.\n\n"
                    "✅ <b>الحل:</b> ضع ملف <code>cookies.txt</code> بجانب البوت.\n"
                    "1️⃣ ادخل يوتيوب من المتصفح بحساب فرعي\n"
                    "2️⃣ نزّل إضافة <i>Get cookies.txt LOCALLY</i>\n"
                    "3️⃣ صدّر الكوكيز من <code>youtube.com</code>\n"
                    "4️⃣ ارفع الملف للسيرفر بنفس مجلد <code>app.py</code>\n\n"
                    "📚 شرح: github.com/yt-dlp/yt-dlp/wiki/FAQ#cookies"
                )
            else:
                await _safe_edit(
                    "🤖 يوتيوب يطلب تحقّق هسّه.\n"
                    "⏳ خلّي ربع ساعة وجرّب مرة ثانية،\n"
                    "أو أرسلها بصيغة ثانية (اسم الأغنية + الفنّان)."
                )
            return

        audio_path, title = result

        # ── التحقق من الحجم النهائي ──
        file_size = os.path.getsize(audio_path)
        if file_size > 50 * 1024 * 1024:
            await _safe_edit(
                f"⚠️ الأغنية كبيرة جداً ({file_size // 1024 // 1024}MB).\n"
                f"🎵 <b>{title[:60]}</b>"
            )
            return

        await _safe_edit("⬆️ يرسل...")
        sent = await message.reply_audio(
            audio      = audio_path,
            title      = title[:60],
            performer  = "🎵 YouTube",
            caption    = f"🎵 <b>{title[:60]}</b>",
            parse_mode = ParseMode.HTML,
        )
        try:
            await wait_msg.delete()
        except Exception:
            pass

        # ── احفظ في الكاش ──
        if sent and sent.audio:
            db_audio_cache_set(query, sent.audio.file_id, title)

    except Exception as e:
        logging.exception("youtube handler error")
        await _safe_edit(f"⚠️ صار خطأ: {str(e)[:150]}")
    finally:
        _shutil.rmtree(tmp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════
#  أمر /chats — يعرض المجموعات والقنوات (للمالك فقط)
# ══════════════════════════════════════════════════════════
@app.on_message(filters.command("chats") & filters.private)
async def list_chats(client: Client, message: Message):
    if message.from_user.id != OWNER_ID:
        return

    with _db_lock:
        conn = get_db()
        rows = conn.execute("SELECT group_id FROM group_settings").fetchall()
        conn.close()

    if not rows:
        await message.reply_text("📭 البوت مو منضم لأي مجموعة حالياً.")
        return

    wait_msg = await message.reply_text("⏳ جاري جلب البيانات...")

    groups_text   = ""
    channels_text = ""
    g_count = 0
    c_count = 0

    for row in rows:
        gid = row[0]
        try:
            chat = await client.get_chat(int(gid))

            # فلتر دقيق — فقط مجموعات وقنوات حقيقية
            if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                continue

            title = chat.title or "بدون اسم"

            # رابط
            if chat.username:
                link      = f"https://t.me/{chat.username}"
                name_part = f'<a href="{link}">{title}</a>'
            else:
                # مجموعة/قناة خاصة — رابط invite إن وجد
                try:
                    invite = await client.export_chat_invite_link(int(gid))
                    name_part = f'<a href="{invite}">{title}</a>'
                except Exception:
                    name_part = f"<b>{title}</b> 🔒"

            # عدد الأعضاء
            try:
                mc = chat.members_count
                members_text = f"👤 {mc:,}" if mc else ""
            except Exception:
                members_text = ""

            line = f"🆔 <code>{gid}</code>"
            if members_text:
                line += f"  |  {members_text}"
            line += "\n"

            if chat.type == ChatType.CHANNEL:
                channels_text += f"📢 {name_part}\n{line}\n"
                c_count += 1
            else:
                groups_text += f"👥 {name_part}\n{line}\n"
                g_count += 1

            # تحديث الاسم في DB
            with _db_lock:
                conn = get_db()
                conn.execute(
                    "UPDATE group_settings SET group_title=? WHERE group_id=?",
                    (title, str(gid))
                )
                conn.commit()
                conn.close()

        except Exception:
            continue

    total = g_count + c_count
    if total == 0:
        try: await wait_msg.delete()
        except: pass
        await message.reply_text("📭 ما لقيت أي مجموعة أو قناة.")
        return

    text = "📋 <b>المجموعات والقنوات:</b>\n━━━━━━━━━━━━━━━━━━\n\n"
    if groups_text:
        text += f"<b>👥 المجموعات ({g_count}):</b>\n{groups_text}"
    if channels_text:
        text += f"<b>📢 القنوات ({c_count}):</b>\n{channels_text}"
    text += f"━━━━━━━━━━━━━━━━━━\n📊 المجموع: <b>{total}</b>  (👥 {g_count}  |  📢 {c_count})"

    try: await wait_msg.delete()
    except: pass
    await message.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@app.on_message(
    filters.text & filters.group & ~filters.bot
    & ~filters.command(["start", "id", "myid", "profile", "bio", "bayo"])
)
async def handle_message(client: Client, message: Message):
    if not message.from_user:
        return
    if message.via_bot:
        return

    user_id   = message.from_user.id
    group_id  = message.chat.id
    fname     = message.from_user.first_name or ""
    text      = message.text.strip()
    t_lower   = text.lower()
    words     = t_lower.split()
    cmd_first = words[0] if words else ""

    _user_sessions.setdefault((group_id, user_id), {})
    is_adm = await is_admin(client, group_id, user_id)

    # ══════════════════════════════════════════════════════════
    #  رد ذكي — يُفعَّل عند مناداة "بوت" أو "ذكي" أو ذكر البوت
    # ══════════════════════════════════════════════════════════
    is_mention = False
    if message.entities:
        for ent in message.entities:
            if ent.type == MessageEntityType.MENTION:
                mentioned = text[ent.offset: ent.offset + ent.length].lstrip("@").lower()
                if mentioned == BOT_USERNAME.lower().lstrip("@"):
                    is_mention = True
                    break

    triggered = (
        text.startswith("بوت")
        or text.startswith("ذكي")
        or is_mention
        or (message.reply_to_message
            and message.reply_to_message.from_user
            and (message.reply_to_message.from_user.is_bot
                 and (message.reply_to_message.from_user.username or "").lower()
                 == BOT_USERNAME.lower().lstrip("@"))
            and not text.startswith("من")
            and not text.startswith("مد")
            and not text.startswith("اد")
            and not text.startswith("م ")
            and not text.startswith("تك")
            and not text.startswith("مط")
            and not text.startswith("كتم")
            and not text.startswith("حظر")
            and not text.startswith("طرد")
            and not text.startswith("تحذير")
        )
    )

    if triggered:
        # فحص الاشتراك — مفروض على الجميع بمن فيهم المشرفين
        if not await check_subscription(client, user_id):
            channel_link = f"https://t.me/{CHANNEL_ID.lstrip('@')}"
            safe = f"@{message.from_user.username}" if message.from_user.username else fname
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("📢 اشترك في القناة", url=channel_link)
            ]])
            try:
                chat = await client.get_chat(CHANNEL_ID)
                if chat.photo:
                    photo = await client.download_media(chat.photo.big_file_id, in_memory=True)
                    photo.seek(0)
                    await message.reply_photo(
                        photo=photo,
                        caption=(
                            f"👋 أهلاً {safe}!\n\n"
                            f"🤖 إذا تريد تتكلم مع <b>ذكي</b> يجب عليك الاشتراك بالقناة أولاً.\n\n"
                            f"✅ بعد الاشتراك أرسل رسالتك مجدداً."
                        ),
                        parse_mode=ParseMode.HTML,
                        reply_markup=kb
                    )
                else:
                    raise Exception("no photo")
            except Exception:
                await message.reply_text(
                    f"👋 أهلاً {safe}!\n\n"
                    f"🤖 إذا تريد تتكلم مع <b>ذكي</b> يجب عليك الاشتراك بالقناة أولاً.\n\n"
                    f"✅ بعد الاشتراك أرسل رسالتك مجدداً.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb
                )
            return

        # استخرج السؤال الفعلي
        if text.startswith("بوت") or text.startswith("ذكي"):
            q = text[4:].strip() if len(text) > 3 and text[3] == " " else text[3:].strip()
        else:
            q = re.sub(rf"@?{re.escape(BOT_USERNAME)}", "", text, flags=re.IGNORECASE).strip()

        if not q:
            await message.reply_text("اكتب سؤالك بعد كلمة 'بوت' او 'ذكي' للتحدث معه🤖..")
            return

        # ── بناء السياق: إذا كان رداً على رسالة شخص آخر ──
        replied = message.reply_to_message
        if (replied and replied.text and replied.from_user
                and not replied.from_user.is_bot):
            sender_name = replied.from_user.first_name or "شخص"
            q = f'[رسالة {sender_name}: "{replied.text}"]\n\nطلب المستخدم: {q}'

        # ── رسالة الانتظار ──
        wait_msg = await message.reply_text("🤔 يفكر...")

        from ai_helper import ask_zaki
        try:
            reply = await ask_zaki(user_id, q, chat_id=group_id)
        except Exception:
            reply = "⚠️ ما قدرت أرد هسّه، جرّب بعدين."

        try:
            await wait_msg.edit_text(reply)
        except Exception:
            try:
                await message.reply_text(reply)
            except Exception:
                pass
        return

    # ================== أقفال الحماية (أعضاء فقط) ==================
    if not is_adm:
        settings = db_get_settings(str(group_id))

        # وضع البطيء
        if settings['slow'] > 0:
            now       = datetime.now()
            grp_cache = slow_mode_cache.setdefault(group_id, {})
            last_time = grp_cache.get(user_id)
            wait_secs = settings['slow']
            if last_time and (now - last_time).total_seconds() < wait_secs:
                remaining = int(wait_secs - (now - last_time).total_seconds())
                safe = f"@{message.from_user.username}" if message.from_user.username else fname
                try: await message.delete()
                except: pass
                w = await client.send_message(
                    group_id,
                    f"🐢 {safe}، الوضع البطيء مفعّل.\n"
                    f"انتظر <b>{remaining}</b> ثانية قبل الإرسال مجدداً.",
                    parse_mode=ParseMode.HTML
                )
                asyncio.create_task(auto_cleanup(client, group_id, w.id))
                return
            grp_cache[user_id] = now
            until = datetime.now(timezone.utc) + timedelta(seconds=wait_secs)
            try:
                await client.restrict_chat_member(
                    group_id, user_id,
                    ChatPermissions(can_send_messages=False), until_date=until
                )
            except: pass

            async def _lift_slow():
                await asyncio.sleep(wait_secs + 1)
                try:
                    await client.restrict_chat_member(
                        group_id, user_id,
                        ChatPermissions(
                            can_send_messages=True, can_send_media_messages=True,
                            can_send_polls=True, can_add_web_page_previews=True,
                            can_invite_users=True,
                        )
                    )
                except: pass
            asyncio.create_task(_lift_slow())

        # سبام / فيضان
        if settings['flood'] == 1:
            now   = datetime.now()
            cache = flood_cache.setdefault(group_id, {})
            entry = cache.setdefault(user_id, {'times': [], 'warnings': 0})
            entry['times'].append(now)
            entry['times'] = [t for t in entry['times'] if now - t < timedelta(seconds=5)]
            if len(entry['times']) >= 5:
                entry['warnings'] += 1
                w_count = entry['warnings']
                safe = f"@{message.from_user.username}" if message.from_user.username else fname
                try: await message.delete()
                except: pass
                if w_count >= 3:
                    until = datetime.now(timezone.utc) + timedelta(minutes=5)
                    try:
                        await client.restrict_chat_member(
                            group_id, user_id,
                            ChatPermissions(can_send_messages=False), until_date=until
                        )
                        db_add_mute(user_id, group_id, until.isoformat())
                        db_log_punishment(user_id, group_id, 0, "كتم 5 دق (فيضان تلقائي)")
                    except: pass
                    entry['warnings'] = 0; entry['times'] = []
                    w = await client.send_message(
                        group_id, f"🔇 {safe} تم كتمك 5 دقائق بسبب الإرسال السريع المتكرر."
                    )
                    asyncio.create_task(auto_cleanup(client, group_id, w.id))
                else:
                    w = await client.send_message(
                        group_id,
                        f"⚠️ تحذير {safe}: توقف عن الإرسال المتكرر السريع. "
                        f"({w_count}/3) — عند 3 سيتم كتمك."
                    )
                    asyncio.create_task(auto_cleanup(client, group_id, w.id))
                return

        # كلايش
        if settings['cliche'] == 1 and (len(text) > 700 or text.count('\n') >= 10):
            try: await message.delete()
            except: pass
            return

        # روابط
        if settings['links'] == 1 and re.search(r'(http://|https://|t\.me/|www\.)', t_lower):
            try: await message.delete()
            except: pass
            return

        # توجيه
        if settings['forward'] == 1 and (
            message.forward_from or message.forward_from_chat or message.forward_sender_name
        ):
            try: await message.delete()
            except: pass
            return

        # معرفات
        if settings['usernames'] == 1 and re.search(r'@\w+', text):
            try: await message.delete()
            except: pass
            return

        # أجنبي
        if settings['foreign'] == 1:
            rank, _ = await get_bot_rank(client, group_id, user_id)
            if rank == 'عضو':
                arabic_c  = len(re.findall(r'[\u0600-\u06FF]', text))
                foreign_c = len(re.findall(r'[گچپژڤێۆیکa-zA-Z]', text))
                if foreign_c > 0 and foreign_c > arabic_c * 0.3:
                    try: await message.delete()
                    except: pass
                    safe = f"@{message.from_user.username}" if message.from_user.username else fname
                    w = await client.send_message(
                        group_id,
                        f"🛑 عذراً {safe}، يُمنع التحدث بغير العربية هنا.\n"
                        f"🌟 للكتابة بلغات أخرى ترقّ إلى رتبة (مميز) أو أعلى."
                    )
                    asyncio.create_task(auto_cleanup(client, group_id, w.id))
                    return

        # فشار
        if settings['bad_words'] == 1 and guard.is_profane(text):
            try: await message.delete()
            except: pass
            return

    # ================== أوامر المشرفين ==================
    if is_adm:
        if t_lower in ["اوامر", "أوامر", "الاوامر", "الأوامر", "امر", "أمر"]:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ أوامر الإدارة",   callback_data='admin_tab'),
                 InlineKeyboardButton("👤 أوامر الأعضاء",  callback_data='user_tab')],
                [InlineKeyboardButton("🎮 التسلية والألعاب", callback_data='games_tab'),
                 InlineKeyboardButton("📊 الإحصائيات",      callback_data='stats_tab')],
                [InlineKeyboardButton("🤖 أوامر الذكاء الاصطناعي", callback_data='ai_tab')],
            ])
            await message.reply_text(
                "📋 <b>قائمة الأوامر</b>\n\nاختر القسم الذي تريده:",
                parse_mode=ParseMode.HTML, reply_markup=kb
            )
            return

        # وضع البطيء
        slow_m = re.match(r'^بطيء\s+(\d+)$', t_lower)
        if slow_m:
            secs = int(slow_m.group(1))
            db_set_setting(str(group_id), 'slow_mode', secs)
            cached_users = list(slow_mode_cache.pop(group_id, {}).keys())
            if secs == 0:
                for uid in cached_users:
                    try:
                        await client.restrict_chat_member(
                            group_id, uid,
                            ChatPermissions(
                                can_send_messages=True, can_send_media_messages=True,
                                can_send_polls=True, can_add_web_page_previews=True,
                                can_invite_users=True,
                            )
                        )
                    except: pass
                await message.reply_text("✅ تم تعطيل الوضع البطيء.")
            else:
                await message.reply_text(f"🐢 تم تفعيل الوضع البطيء: {secs} ثانية بين كل رسالة.")
            return

        if t_lower in ["فتح البطيء", "بطيء 0", "تعطيل البطيء"]:
            db_set_setting(str(group_id), 'slow_mode', 0)
            for uid in list(slow_mode_cache.pop(group_id, {}).keys()):
                try:
                    await client.restrict_chat_member(
                        group_id, uid,
                        ChatPermissions(
                            can_send_messages=True, can_send_media_messages=True,
                            can_send_polls=True, can_add_web_page_previews=True,
                            can_invite_users=True,
                        )
                    )
                except: pass
            await message.reply_text("✅ تم تعطيل الوضع البطيء.")
            return

        # أقفال
        locks_map = {
            'الروابط':   'lock_links',    'ر':      'lock_links',
            'الكلايش':   'lock_cliche',   'ش':      'lock_cliche',
            'التوجيه':   'lock_forward',  'ت_قفل':  'lock_forward',
            'المعرفات':  'lock_usernames','م_قفل':  'lock_usernames',
            'التكرار':   'lock_flood',    'ك':      'lock_flood',
            'الاجنبي':   'lock_foreign',  'الأجنبي':'lock_foreign',  'ج': 'lock_foreign',
            'الفشار':    'filter_bad_words','ف':    'filter_bad_words','الحماية':'filter_bad_words',
        }
        lock_m = re.match(r'^(قفل|فتح)\s+(.+)$', t_lower)
        if lock_m:
            action, tgt = lock_m.group(1), lock_m.group(2).strip()
            key = tgt if tgt in locks_map else None
            if key:
                val = 1 if action == 'قفل' else 0
                db_set_setting(str(group_id), locks_map[key], val)
                await message.reply_text(f"{'🔒 تم قفل' if val else '🔓 تم فتح'} {tgt}.")
                return

        # صور البروفايل
        if t_lower in ["تعط", "تعطيل الصور"]:
            db_set_setting(str(group_id), 'photo_profile', 0)
            await message.reply_text("🚫 تم تعطيل صور البروفايل."); return
        if t_lower in ["تفع", "تفعيل الصور"]:
            db_set_setting(str(group_id), 'photo_profile', 1)
            await message.reply_text("✅ تم تفعيل صور البروفايل."); return

        # الهمسة
        if t_lower in ["تفعيل الهمسة", "هم تفعيل", "تفعيل هم"]:
            db_set_setting(str(group_id), 'whisper_enabled', 1)
            await message.reply_text("🤫 تم تفعيل ميزة الهمسة."); return
        if t_lower in ["تعطيل الهمسة", "هم تعطيل", "تعطيل هم"]:
            db_set_setting(str(group_id), 'whisper_enabled', 0)
            await message.reply_text("🔇 تم تعطيل ميزة الهمسة."); return

        # ── حذف الميديا التلقائي ──
        if t_lower in ["تفع حذف", "تفعيل حذف", "تفعيل الحذف"]:
            db_set_setting(str(group_id), 'auto_delete_media', 1)
            await message.reply_text(
                "🗑️ <b>تم تفعيل الحذف التلقائي للميديا</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "• سيتم حذف الصور والمقاطع والملصقات والمتحركات\n"
                "• بعد <b>5 دقائق</b> من إرسالها\n"
                "• ✅ رسائل المثبتات محمية من الحذف",
                parse_mode=ParseMode.HTML); return

        if t_lower in ["تعط حذف", "تعطيل حذف", "تعطيل الحذف"]:
            db_set_setting(str(group_id), 'auto_delete_media', 0)
            await message.reply_text("✅ تم تعطيل الحذف التلقائي للميديا."); return

        # المكتومون
        if cmd_first == "المكتومين":
            await cmd_muted_list(client, message); return
        if cmd_first == "مسح" and len(words) > 1 and words[1] == "المكتومين":
            await cmd_clear_mutes(client, message); return

        # حذف رسائل  ─  مسح [رقم]  (يقبل أرقاماً عربية وإنجليزية)
        if cmd_first == "مسح" and len(words) >= 2:
            # ── تحويل الأرقام العربية-الهندية إلى أرقام إنجليزية ──
            raw_n = words[1].translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
            try:
                n = int(raw_n)
                if n <= 0:
                    raise ValueError
            except ValueError:
                # ليس رقماً → نتجاوز لبقية الأوامر (مسح التحذيرات…)
                pass
            else:
                n = min(n, 200)   # حد أقصى 200 رسالة

                # ── get_chat_history ممنوع على البوتات → نستخدم get_messages ──
                # معرّفات تيليغرام تسلسلية، فنحسب نطاقاً كافياً قبل رسالة الأمر
                current_id = message.id
                lookback   = min(n * 4 + 50, 400)          # احتياطي لتجاوز الفجوات
                start_id   = max(1, current_id - lookback)
                cand_ids   = list(range(start_id, current_id))

                valid_ids = []
                fetch_err = None

                for i in range(0, len(cand_ids), 200):     # get_messages: حد 200 في المرة
                    chunk = cand_ids[i:i + 200]
                    try:
                        fetched = await client.get_messages(group_id, chunk)
                        msgs = fetched if isinstance(fetched, list) else [fetched]
                        for m in msgs:
                            if m and not m.empty:
                                valid_ids.append(m.id)
                    except Exception as e:
                        fetch_err = str(e)[:150]
                        break

                if not valid_ids and fetch_err:
                    await message.reply_text(
                        f"⚠️ تعذّر جلب الرسائل:\n<code>{fetch_err}</code>",
                        parse_mode=ParseMode.HTML
                    )
                    return

                # أحدث n رسالة (أعلى معرّفات)
                valid_ids.sort(reverse=True)
                ids_to_del = valid_ids[:n]

                # ── حذف أمر المشرف أولاً ──
                try:
                    await message.delete()
                except Exception:
                    pass

                # ── حذف الرسائل (100 كحد أقصى لكل طلب) ──
                deleted = 0
                for i in range(0, len(ids_to_del), 100):
                    try:
                        await client.delete_messages(group_id, ids_to_del[i:i + 100])
                        deleted += len(ids_to_del[i:i + 100])
                    except Exception:
                        pass

                # ── إشعار النتيجة ──
                if deleted:
                    notif_text = f"🗑️ تم حذف <b>{deleted}</b> رسالة."
                else:
                    notif_text = (
                        "⚠️ لم يتم حذف أي رسالة.\n"
                        "تأكد أن البوت مشرف ولديه صلاحية حذف الرسائل."
                    )
                r = await client.send_message(group_id, notif_text, parse_mode=ParseMode.HTML)
                asyncio.create_task(auto_cleanup(client, group_id, r.id))
                return

        # إحصاء
        if cmd_first in ["احصاء", "إحصاء", "إحصائيات", "احصائيات", "ستات"]:
            await cmd_group_stats(client, message); return

        # عقوبات
        if cmd_first == "عقوبات":
            await cmd_punishments(client, message); return

        # مسح التحذيرات
        if cmd_first == "مسح" and len(words) > 1 and words[1] == "التحذيرات":
            t_id, t_name = await get_target_from_args(client, message)
            if t_id:
                db_clear_warnings(t_id, group_id)
                await message.reply_text(f"✅ تم مسح تحذيرات {t_name}.")
            return

        # أوامر الهدف
        # الأوامر القصيرة (م، اد، مد، من، تك) تشتغل فقط إذا:
        # ١- الرسالة كلمة واحدة فقط، أو
        # ٢- الرسالة ريبلاي على عضو، أو تحتوي على @منشن
        _short_rank_cmds = {"م", "اد", "مد", "من", "تك", "مط"}
        _has_target = (
            (message.reply_to_message and message.reply_to_message.from_user)
            or any(
                e.type in (MessageEntityType.MENTION, MessageEntityType.TEXT_MENTION)
                for e in (message.entities or [])
            )
            or any(w.startswith('@') for w in words)
        )

        admin_cmds = ["كتم", "حظر", "طرد", "تحذير", "م", "اد", "مد", "من", "تك"]
        cmd_found  = None
        if cmd_first in admin_cmds:
            if cmd_first in _short_rank_cmds:
                if len(words) == 1:
                    cmd_found = cmd_first
            else:
                cmd_found = cmd_first
        if cmd_first == "الغاء" and len(words) > 1 and words[1] == "الكتم":
            cmd_found = "الغاء الكتم"
        if cmd_first == "مط" and user_id == OWNER_ID:
            if len(words) == 1:
                cmd_found = "مط"

        if cmd_found:
            t_id, t_name = await get_target_from_args(client, message)
            if not t_id:
                await message.reply_text(
                    "⚠️ تعذّر تنفيذ الأمر.\n\n"
                    "استخدم الرد المباشر على رسالة العضو، أو تأكد من صحة اليوزر."
                )
                return

            if cmd_found == "كتم":
                duration = None
                for w in words:
                    try: duration = int(w); break
                    except: pass
                if duration:
                    until = datetime.now(timezone.utc) + timedelta(minutes=duration)
                    ok = await _exec_admin_action(
                        client, message,
                        client.restrict_chat_member(
                            group_id, t_id,
                            ChatPermissions(can_send_messages=False), until_date=until
                        ),
                        f"🔇 تم كتم {t_name} مؤقتاً لمدة {duration} دقيقة."
                    )
                    if ok:
                        db_add_mute(t_id, group_id, until.isoformat())
                        db_log_punishment(t_id, group_id, user_id, f"كتم مؤقت {duration} دقيقة")
                else:
                    ok = await _exec_admin_action(
                        client, message,
                        client.restrict_chat_member(
                            group_id, t_id, ChatPermissions(can_send_messages=False)
                        ),
                        f"🔇 تم كتم {t_name} بشكل دائم."
                    )
                    if ok:
                        db_add_mute(t_id, group_id)
                        db_log_punishment(t_id, group_id, user_id, "كتم دائم")

            elif cmd_found == "الغاء الكتم":
                ok = await _exec_admin_action(
                    client, message,
                    client.restrict_chat_member(
                        group_id, t_id,
                        ChatPermissions(
                            can_send_messages=True, can_send_media_messages=True,
                            can_send_polls=True, can_add_web_page_previews=True,
                            can_invite_users=True,
                        )
                    ),
                    f"🔊 تم إلغاء كتم {t_name}."
                )
                if ok:
                    db_remove_mute(t_id, group_id)
                    db_log_punishment(t_id, group_id, user_id, "إلغاء كتم")

            elif cmd_found == "تحذير":
                target_is_adm = await is_admin(client, group_id, t_id)
                if target_is_adm:
                    await message.reply_text(f"⚠️ لا يمكن تحذير {t_name} لأنه مشرف أو مالك.")
                    return
                target_rank, _ = await get_bot_rank(client, group_id, t_id)
                if target_rank not in ['عضو', 'مميز']:
                    await message.reply_text(f"⚠️ لا يمكن تحذير {t_name} — رتبته: {target_rank}.")
                    return
                count = db_add_warning(t_id, group_id)
                db_log_punishment(t_id, group_id, user_id, f"تحذير ({count}/3)")
                if count >= 3:
                    ok = await _exec_admin_action(
                        client, message,
                        client.restrict_chat_member(
                            group_id, t_id, ChatPermissions(can_send_messages=False)
                        ),
                        f"🔇 {t_name} وصل لـ 3 تحذيرات — تم كتمه تلقائياً."
                    )
                    if ok:
                        db_add_mute(t_id, group_id)
                        db_clear_warnings(t_id, group_id)
                        db_log_punishment(t_id, group_id, user_id, "كتم تلقائي (3 تحذيرات)")
                else:
                    extra = "\n🔇 تحذير واحد آخر = كتم تلقائي!" if count == 2 else ""
                    await message.reply_text(f"⚠️ تحذير {count}/3 لـ {t_name}.{extra}")

            elif cmd_found == "حظر":
                ok = await _exec_admin_action(
                    client, message,
                    client.ban_chat_member(group_id, t_id),
                    f"🚫 تم حظر {t_name}."
                )
                if ok: db_log_punishment(t_id, group_id, user_id, "حظر")

            elif cmd_found == "طرد":
                try:
                    await client.ban_chat_member(group_id, t_id)
                    await client.unban_chat_member(group_id, t_id)
                    await message.reply_text(f"👢 تم طرد {t_name}.")
                    db_log_punishment(t_id, group_id, user_id, "طرد")
                except Exception as e:
                    await message.reply_text(
                        f"⚠️ فشل تنفيذ الأمر:\n<code>{str(e)[:200]}</code>",
                        parse_mode=ParseMode.HTML
                    )

            elif cmd_found in ["م", "اد", "مد", "من", "مط"]:
                rank_names = {"م":"مميز","اد":"ادمن","مد":"مدير","من":"منشئ","مط":"مطور"}
                new_rank   = rank_names[cmd_found]
                with _db_lock:
                    conn = get_db()
                    conn.execute(
                        "INSERT OR REPLACE INTO ranks (user_id, group_id, rank) VALUES (?, ?, ?)",
                        (t_id, group_id, new_rank)
                    )
                    conn.commit(); conn.close()
                await message.reply_text(f"✅ تم رفع {t_name} إلى رتبة {new_rank}.")
                db_log_punishment(t_id, group_id, user_id, f"رفع رتبة → {new_rank}")

            elif cmd_found == "تك":
                with _db_lock:
                    conn = get_db()
                    conn.execute(
                        "DELETE FROM ranks WHERE user_id=? AND group_id=?", (t_id, group_id)
                    )
                    conn.commit(); conn.close()
                await message.reply_text(f"✅ تم تنزيل {t_name} إلى رتبة 'عضو'.")
                db_log_punishment(t_id, group_id, user_id, "تنزيل رتبة → عضو")
            return

        # تعطيل/تفعيل النداء
        if t_lower == "تعطيل النداء":
            db_set_setting(str(group_id), 'ndaa_enabled', 0)
            await message.reply_text("🔇 تم تعطيل أمر النداء وتاك للكل.")
            return
        if t_lower == "تفعيل النداء":
            db_set_setting(str(group_id), 'ndaa_enabled', 1)
            await message.reply_text("✅ تم تفعيل أمر النداء وتاك للكل.")
            return

        # ══════════════ تاك تلقائي (للمشرفين فقط) ══════════════
        if t_lower in ["تاك تلقائي", "تاك", "tag"]:
            cancel_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_auto_tag|{user_id}")
            ]])
            r = await message.reply_text(
                "📢 <b>تاك تلقائي</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                "✏️ <b>المرحلة 1/2</b> — اكتب نص الكليشة التي تريد إرسالها:\n\n"
                "<i>مثال: تعالوا راح نبدأ نلعب</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=cancel_kb
            )
            pending_auto_tag[user_id] = {
                "stage": 1,
                "group_id": group_id,
                "req_msg_id": r.id,
            }

            async def _expire_auto_tag():
                await asyncio.sleep(300)
                if user_id in pending_auto_tag:
                    mid = pending_auto_tag[user_id].get("req_msg_id")
                    if mid:
                        try: await client.edit_message_text(group_id, mid, "⏰ انتهت جلسة التاك التلقائي.")
                        except: pass
                    pending_auto_tag.pop(user_id, None)
            asyncio.create_task(_expire_auto_tag())
            return

    # ================== تاك تلقائي — معالجة الجلسة ==================

    if user_id in pending_auto_tag:
        pat = pending_auto_tag[user_id]
        if group_id == pat.get("group_id"):
            stage = pat.get("stage", 1)
            cancel_kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_auto_tag|{user_id}")
            ]])

            # المرحلة 1: المشرف يكتب نص الكليشة
            if stage == 1:
                if "req_msg_id" in pat:
                    try: await client.delete_messages(group_id, pat["req_msg_id"])
                    except: pass
                tag_text = text.strip()
                if not tag_text:
                    r = await message.reply_text(
                        "⚠️ النص فارغ، أرسل نص الكليشة مجدداً.",
                        reply_markup=cancel_kb
                    )
                    pat["req_msg_id"] = r.id
                    return
                pat["tag_text"] = tag_text
                pat["stage"] = 2
                preview = tag_text[:100]
                r = await message.reply_text(
                    f"✅ <b>تم حفظ نص الكليشة:</b>\n<i>{preview}</i>\n\n"
                    "━━━━━━━━━━━━━━━━━━\n"
                    "👥 <b>المرحلة 2/2</b> — اكتب عدد الأشخاص الذين تريد إرسال الرسالة إليهم\n"
                    "<i>(الحد الأقصى 200 شخص)</i>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=cancel_kb
                )
                pat["req_msg_id"] = r.id
                return

            # المرحلة 2: المشرف يكتب العدد → إرسال الكليشة
            elif stage == 2:
                if "req_msg_id" in pat:
                    try: await client.delete_messages(group_id, pat["req_msg_id"])
                    except: pass
                raw_count = text.strip().translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
                try:
                    count = int(raw_count)
                    if count <= 0:
                        raise ValueError
                except ValueError:
                    r = await message.reply_text(
                        "⚠️ أرسل رقماً صحيحاً أكبر من صفر.",
                        reply_markup=cancel_kb
                    )
                    pat["req_msg_id"] = r.id
                    return

                count = min(count, 200)
                tag_text = pat.get("tag_text", "")
                pending_auto_tag.pop(user_id, None)

                # جلب أعضاء المجموعة
                members_found = []
                try:
                    async for member in client.get_chat_members(group_id):
                        if len(members_found) >= count:
                            break
                        u = member.user
                        if u.is_bot or u.id == user_id:
                            continue
                        members_found.append(u)
                except Exception as e:
                    await message.reply_text(
                        f"⚠️ فشل جلب الأعضاء:\n<code>{str(e)[:150]}</code>",
                        parse_mode=ParseMode.HTML
                    )
                    return

                if not members_found:
                    await message.reply_text("⚠️ لم يتم العثور على أعضاء في المجموعة.")
                    return

                # حذف رسالة الأمر
                try: await message.delete()
                except: pass

                # بناء ذكر صامت لكل عضو (zero-width space)
                mentions = " ".join(
                    f'<a href="tg://user?id={u.id}"></a>' for u in members_found
                )
                await client.send_message(
                    group_id,
                    f"{tag_text}\n{mentions}",
                    parse_mode=ParseMode.HTML
                )

                # إشعار النتيجة للمجموعة
                suffix = "..." if len(tag_text) > 60 else ""
                notif = await client.send_message(
                    group_id,
                    f"✅ <b>تم إرسال التاك التلقائي</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"📢 النص: <i>{tag_text[:60]}{suffix}</i>\n"
                    f"👥 عدد المُستدعَين: <b>{len(members_found)}</b> شخص",
                    parse_mode=ParseMode.HTML
                )
                asyncio.create_task(auto_cleanup(client, group_id, notif.id))
                return

    # ================== نظام الردود المخصصة ==================

    # --- معالجة جلسة حذف الرد ---
    if user_id in pending_delete_replies:
        pending_del = pending_delete_replies[user_id]
        if group_id == pending_del['group_id']:
            if 'req_msg_id' in pending_del:
                try: await client.delete_messages(group_id, pending_del['req_msg_id'])
                except: pass
            name_to_delete = text.strip().lstrip('@')
            found = db_find_reply_by_name(name_to_delete)
            if found:
                db_delete_reply(found[0])
                await message.reply_text(f"✅ تم حذف رد <b>{found[1]}</b> بنجاح.", parse_mode=ParseMode.HTML)
            else:
                await message.reply_text(f"⚠️ لا يوجد رد باسم <b>{name_to_delete}</b>.", parse_mode=ParseMode.HTML)
            pending_delete_replies.pop(user_id, None)
            return

    # --- معالجة جلسة إضافة الرد (متعددة المراحل) ---
    if user_id in pending_replies:
        pending = pending_replies[user_id]
        if group_id == pending.get('group_id'):
            stage = pending.get('stage', 3)

            # المرحلة 1: الأدمن يُرسل @يوزر الشخص المستهدف
            if stage == 1:
                if 'req_msg_id' in pending:
                    try: await client.delete_messages(group_id, pending['req_msg_id'])
                    except: pass
                target_user_id = None
                target_display = None
                target_tg_username = ""
                # محاولة استخراج الهدف من الريبلاي
                if message.reply_to_message and message.reply_to_message.from_user:
                    tu = message.reply_to_message.from_user
                    target_user_id    = tu.id
                    target_tg_username = tu.username or ""
                    target_display    = tu.first_name or "المستخدم"
                else:
                    # من entity أو نص مباشر
                    raw = text.strip().lstrip('@')
                    for entity in (message.entities or []):
                        if entity.type == MessageEntityType.TEXT_MENTION and entity.user:
                            target_user_id    = entity.user.id
                            target_tg_username = entity.user.username or ""
                            target_display    = entity.user.first_name or "المستخدم"
                            break
                        elif entity.type == MessageEntityType.MENTION:
                            uname = _extract_entity_text(message.text, entity).lstrip('@')
                            try:
                                tu = await client.get_users(uname)
                                target_user_id    = tu.id
                                target_tg_username = tu.username or ""
                                target_display    = tu.first_name or "المستخدم"
                            except: pass
                            break
                    if not target_user_id and raw:
                        try:
                            tu = await client.get_users(raw)
                            target_user_id    = tu.id
                            target_tg_username = tu.username or ""
                            target_display    = tu.first_name or "المستخدم"
                        except: pass
                if not target_user_id:
                    r = await message.reply_text(
                        "⚠️ لم أتمكن من إيجاد المستخدم.\n"
                        "أرسل @يوزره مرة أخرى أو ارد مباشرة على إحدى رسائله.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_reply|{user_id}")
                        ]])
                    )
                    pending['req_msg_id'] = r.id
                    return
                existing = db_get_reply(target_user_id)
                if existing:
                    note = f"\n\n⚠️ لديه رد مسبق باسم: <b>{existing[0]}</b> — سيُستبدل."
                else:
                    note = ""
                r = await message.reply_text(
                    f"📝 <b>ما اسم الرد لـ {target_display}؟</b>{note}\n\n"
                    "اكتب الكلمة التي ستُشغّل الرد (مثل: <i>جوجو</i>).",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_reply|{user_id}")
                    ]])
                )
                pending.update({
                    'stage': 2, 'req_msg_id': r.id,
                    'target_user_id': target_user_id,
                    'target_tg_username': target_tg_username,
                    'target_display': target_display,
                })
                return

            # المرحلة 2: الأدمن يكتب اسم الرد (الكلمة المُشغِّلة)
            elif stage == 2:
                if 'req_msg_id' in pending:
                    try: await client.delete_messages(group_id, pending['req_msg_id'])
                    except: pass
                trigger_name = text.strip()
                if not trigger_name:
                    r = await message.reply_text(
                        "⚠️ اسم غير صالح، أرسل الاسم مجدداً.",
                        reply_markup=InlineKeyboardMarkup([[
                            InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_reply|{user_id}")
                        ]])
                    )
                    pending['req_msg_id'] = r.id
                    return
                pending['trigger_name'] = trigger_name
                pending['stage'] = 3
                r = await message.reply_text(
                    f"💬 <b>ما نص الرد لـ {pending['target_display']}؟</b>\n\n"
                    "اكتب النص، أو أرسل صورة/فيديو (مع تعليق اختياري).",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🚫 بدون نص", callback_data=f"no_text_reply|{user_id}"),
                        InlineKeyboardButton("❌ إلغاء",   callback_data=f"cancel_reply|{user_id}"),
                    ]])
                )
                pending['req_msg_id'] = r.id
                return

            # المرحلة 3: الأدمن يكتب نص الرد → حفظ
            elif stage == 3:
                if 'req_msg_id' in pending:
                    try: await client.delete_messages(group_id, pending['req_msg_id'])
                    except: pass
                db_add_reply(
                    pending['target_user_id'],
                    pending['trigger_name'],
                    text,
                    pending['target_tg_username'],
                )
                preview = text[:40] + ('...' if len(text) > 40 else '')
                await message.reply_text(
                    f"✅ <b>تم حفظ الرد بنجاح!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"👤 الشخص: {pending['target_display']}\n"
                    f"🔑 الاسم المُشغِّل: <b>{pending['trigger_name']}</b>\n"
                    f"💬 النص: {preview}",
                    parse_mode=ParseMode.HTML
                )
                pending_replies.pop(user_id, None)
                return

    if t_lower.startswith(("اضف رد", "إضافة رد", "اضافه رد")):
        if not is_adm:
            m = await message.reply_text("⚠️ يجب عليك ان تكون ادمن على الأقل لإضافة الردود.")
            asyncio.create_task(auto_cleanup(client, group_id, message.id, m.id))
            return

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_reply|{user_id}")]])

        # محاولة معرفة الهدف من الريبلاي أو @يوزر في الأمر ذاته
        target_user_id = None; target_display = None; target_tg_username = ""

        if message.reply_to_message and message.reply_to_message.from_user:
            tu = message.reply_to_message.from_user
            target_user_id = tu.id
            target_tg_username = tu.username or ""
            target_display = tu.first_name or "المستخدم"
        elif len(words) >= 2:
            mention = words[1].lstrip('@')
            try:
                tu = await client.get_users(mention)
                target_user_id = tu.id
                target_tg_username = tu.username or ""
                target_display = tu.first_name or "المستخدم"
            except: pass

        if target_user_id:
            # الهدف معروف → انتقل مباشرة للمرحلة 2 (اسم الرد)
            existing = db_get_reply(target_user_id)
            note = f"\n\n⚠️ لديه رد مسبق باسم: <b>{existing[0]}</b> — سيُستبدل." if existing else ""
            r = await message.reply_text(
                f"📝 <b>ما اسم الرد لـ {target_display}؟</b>{note}\n\n"
                "اكتب الكلمة التي ستُشغّل الرد (مثل: <i>جوجو</i>).",
                parse_mode=ParseMode.HTML, reply_markup=kb
            )
            pending_replies[user_id] = {
                'stage': 2, 'group_id': group_id, 'req_msg_id': r.id,
                'target_user_id': target_user_id,
                'target_tg_username': target_tg_username,
                'target_display': target_display,
            }
        else:
            # الهدف مجهول → المرحلة 1 (اطلب @يوزر)
            r = await message.reply_text(
                "👤 <b>لمن تريد إضافة الرد؟</b>\n\n"
                "أرسل @يوزر الشخص، أو ارد مباشرة على إحدى رسائله.",
                parse_mode=ParseMode.HTML, reply_markup=kb
            )
            pending_replies[user_id] = {'stage': 1, 'group_id': group_id, 'req_msg_id': r.id}

        async def _expire_add():
            await asyncio.sleep(300)
            if user_id in pending_replies:
                mid = pending_replies[user_id].get('req_msg_id')
                if mid:
                    try: await client.edit_message_text(group_id, mid, "⏰ انتهت الجلسة.")
                    except: pass
                pending_replies.pop(user_id, None)
        asyncio.create_task(_expire_add())
        return

    if t_lower in ("الردود", "ردود"):
        replies = db_get_all_replies()
        if not replies:
            await message.reply_text("📋 لا توجد ردود مخصصة حالياً.")
        else:
            lines = []
            for idx, r in enumerate(replies, 1):
                trigger = r['username']
                tg_uname = r['tg_username']
                person = f"@{tg_uname}" if tg_uname else "—"
                preview = r['reply_text'][:35] + ('...' if len(r['reply_text']) > 35 else '')
                lines.append(
                    f"┌ <b>{idx}. {trigger}</b> ← {person}\n"
                    f"└ 💬 {preview}"
                )
            header = f"📋 <b>قائمة الردود</b> — {len(replies)} رد\n{'━' * 20}\n\n"
            await message.reply_text(header + "\n\n".join(lines), parse_mode=ParseMode.HTML)
        return

    # ----- أمر مسح رد (للأدمن) -----
    if t_lower.startswith(("مسح رد", "حذف رد")):
        if not is_adm:
            m = await message.reply_text("⚠️ يجب أن تكون ادمن لاستخدام هذا الأمر.")
            asyncio.create_task(auto_cleanup(client, group_id, message.id, m.id))
            return

        # الحالة 1: رد مباشر على رسالة الشخص
        if message.reply_to_message and message.reply_to_message.from_user:
            target_id = message.reply_to_message.from_user.id
            if db_get_reply(target_id):
                db_delete_reply(target_id)
                await message.reply_text("✅ تم حذف الرد بنجاح.")
            else:
                await message.reply_text("⚠️ هذا الشخص ليس لديه رد مخصص.")
            return

        # الحالة 2: "مسح رد اسم_اليوزر" مباشرة في نفس الرسالة
        # الكلمات: ["مسح","رد","username"] — نحتاج على الأقل 3 كلمات
        if len(words) >= 3:
            mention = words[2].lstrip('@')
            found = db_find_reply_by_name(mention.lower())
            if found:
                db_delete_reply(found[0])
                await message.reply_text(f"✅ تم حذف رد <b>{found[1]}</b> بنجاح.", parse_mode=ParseMode.HTML)
            else:
                await message.reply_text(f"⚠️ لا يوجد رد باسم <b>{mention}</b>.", parse_mode=ParseMode.HTML)
            return

        # الحالة 3: "مسح رد" بدون اسم — نسأل الأدمن ونتوقع ردّه
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_del_reply|{user_id}")
        ]])
        r = await message.reply_text(
            "🗑️ <b>ما اسم الرد الذي تريد حذفه؟</b>\n\n"
            "اكتب اسم اليوزر الآن، أو أرسل الرسالة بالرد المباشر على الشخص.",
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )
        pending_delete_replies[user_id] = {'group_id': group_id, 'req_msg_id': r.id}

        async def _expire_del():
            await asyncio.sleep(120)
            if user_id in pending_delete_replies:
                try: await client.edit_message_text(group_id, r.id, "⏰ انتهت الجلسة.")
                except: pass
                pending_delete_replies.pop(user_id, None)
        asyncio.create_task(_expire_del())
        return

    # ================== أوامر الأعضاء ==================
    if t_lower in ["العاب", "الالعاب", "الألعاب"]:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 عرض أوامر الألعاب", callback_data="games_tab")]
        ])
        await message.reply_text(
            "🎮 <b>الألعاب والتسلية</b>\nاضغط على الزر لاستعراض جميع الألعاب وطريقة اللعب.",
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )
        return

    if message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.MENTION:
                mentioned = _extract_entity_text(message.text, entity)
                if mentioned.lower() == f"@{BOT_USERNAME.lower()}":
                    await message.reply_text(
                        "في خدمتك! 🤖\nاكتب <b>بوت</b> أو <b>ذكي</b> ثم سؤالك.",
                        parse_mode=ParseMode.HTML
                    )
                    return

    if cmd_first in PROFILE_COMMANDS: await cmd_profile(client, message); return
    if cmd_first in BIO_COMMANDS:     await cmd_bio(client, message);     return

    if cmd_first == "عقوباتي":
        await cmd_punishments(client, message, for_self=True); return

    if cmd_first in ["احصاء", "إحصاء", "إحصائيات", "احصائيات", "ستات"]:
        await cmd_group_stats(client, message); return

    if cmd_first in ["ر", "رتبتي"]:
        rank, _ = await get_bot_rank(client, group_id, user_id)
        r = await message.reply_text(f"👑 رتبتك: {rank}")
        asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id)); return

    if cmd_first == "ن":
        coins, _, _ = db_get_user(user_id, group_id, fname)
        r = await message.reply_text(f"💰 رصيدك: {coins} عملة")
        asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id)); return

    if cmd_first == "ت":
        with _db_lock:
            conn = get_db()
            rows = conn.execute(
                "SELECT user_id, first_name, xp FROM users WHERE group_id=? ORDER BY xp DESC LIMIT 5",
                (group_id,)
            ).fetchall()
            conn.close()
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
        lines  = []
        for i, row in enumerate(rows):
            uid, fn, xp = row[0], row[1], row[2]
            try:
                m    = await client.get_chat_member(group_id, uid)
                name = m.user.first_name or fn or str(uid)
            except: name = fn or str(uid)
            lines.append(f"{medals[i]} {name} — {xp} نقطة")
        await message.reply_text(
            "🏆 <b>الأكثر تفاعلاً:</b>\n━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines),
            parse_mode=ParseMode.HTML
        )
        return

    # --- أوامر الرتب الجديدة ---
    if cmd_first == "المميزين":
        members = await get_members_by_rank(client, group_id, "مميز")
        if members:
            text = "⭐ <b>المميزين:</b>\n━━━━━━━━━━━━━━━━━━\n" + "\n".join(f"• {m}" for m in members)
        else:
            text = "⭐ <b>المميزين:</b>\n━━━━━━━━━━━━━━━━━━\nلا يوجد مميزين حالياً."
        await message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    if cmd_first == "الادمنية":
        members = await get_members_by_rank(client, group_id, "ادمن")
        if members:
            text = "⚙️ <b>الأدمنية:</b>\n━━━━━━━━━━━━━━━━━━\n" + "\n".join(f"• {m}" for m in members)
        else:
            text = "⚙️ <b>الأدمنية:</b>\n━━━━━━━━━━━━━━━━━━\nلا يوجد أدمنية حالياً."
        await message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    if cmd_first == "المدراء":
        members = await get_members_by_rank(client, group_id, "مدير")
        if members:
            text = "👔 <b>المدراء:</b>\n━━━━━━━━━━━━━━━━━━\n" + "\n".join(f"• {m}" for m in members)
        else:
            text = "👔 <b>المدراء:</b>\n━━━━━━━━━━━━━━━━━━\nلا يوجد مدراء حالياً."
        await message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    if cmd_first == "المشرفين":
        admins = []
        try:
            async for member in client.get_chat_members(group_id, filter=ChatMembersFilter.ADMINISTRATORS):
                user = member.user
                if user.is_bot:
                    continue
                name = f"@{user.username}" if user.username else user.first_name or str(user.id)
                admins.append(name)
        except:
            pass
        if admins:
            text = "🛡️ <b>المشرفون:</b>\n━━━━━━━━━━━━━━━━━━\n" + "\n".join(f"• {m}" for m in admins)
        else:
            text = "🛡️ <b>المشرفون:</b>\n━━━━━━━━━━━━━━━━━━\nلا يوجد مشرفين حالياً."
        await message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    if cmd_first == "المالك":
        owner = None
        try:
            # نبحث عن المالك من خلال فحص حالة كل الأعضاء
            async for member in client.get_chat_members(group_id):
                if member.status == ChatMemberStatus.OWNER:
                    user = member.user
                    owner = f"@{user.username}" if user.username else user.first_name or str(user.id)
                    break
        except Exception as e:
            logging.warning(f"فشل جلب المالك: {e}")
        if owner:
            text = f"👑 <b>مالك المجموعة:</b>\n━━━━━━━━━━━━━━━━━━\n• {owner}"
        else:
            text = "👑 <b>مالك المجموعة:</b>\n━━━━━━━━━━━━━━━━━━\nلم يتم العثور على المالك."
        await message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    if cmd_first == "المطور":
        await message.reply_text(
            "🔧 <b>مطور البوت:</b>\n━━━━━━━━━━━━━━━━━━\n• @Laith_jamal",
            parse_mode=ParseMode.HTML
        )
        return

    # --- أمر النداء ---
    if cmd_first in ["نداء", "نن", "ند"]:
        settings = db_get_settings(str(group_id))
        if settings.get('ndaa', 1) == 0:
            r = await message.reply_text("🔇 أمر النداء معطّل في هذه المجموعة.")
            asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
            return
        # ── فحص الصلاحية: مميز فما فوق ──
        _ALLOWED_NDA = {'مميز','ادمن','مدير','منشئ','مطور','مشرف','مالك','المعمار'}
        _nda_rank, _ = await get_bot_rank(client, group_id, user_id)
        if _nda_rank not in _ALLOWED_NDA:
            r = await message.reply_text("⛔ هذا الأمر مخصص للمميزين فما فوق فقط.")
            asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
            return
        target = await get_random_member(client, group_id, exclude_user_id=user_id)
        if not target:
            await message.reply_text("⚠️ لا يوجد أعضاء متاحين للنداء حالياً.")
            return
        mention = f'<a href="tg://user?id={target.id}">{target.first_name or "العضو"}</a>'
        phrase = random.choice(NDA_MESSAGES)
        await message.reply_text(
            f"📢 <b>نداء عشوائي!</b>\n━━━━━━━━━━━━━━━━━━\n"
            f"{mention}\n\n"
            f"{phrase}",
            parse_mode=ParseMode.HTML
        )
        return

    # --- أمر تاك للكل ---
    if len(words) >= 2 and words[0] == "تاك" and words[1] == "للكل":
        settings = db_get_settings(str(group_id))
        if settings.get('ndaa', 1) == 0:
            r = await message.reply_text("🔇 أمر تاك للكل معطّل في هذه المجموعة.")
            asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
            return
        # ── فحص الصلاحية: مميز فما فوق ──
        _ALLOWED_TAG = {'مميز','ادمن','مدير','منشئ','مطور','مشرف','مالك','المعمار'}
        _tag_rank, _ = await get_bot_rank(client, group_id, user_id)
        if _tag_rank not in _ALLOWED_TAG:
            r = await message.reply_text("⛔ هذا الأمر مخصص للمميزين فما فوق فقط.")
            asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
            return

        def _make_mention(uid: int, name: str) -> str:
            """منشن حقيقي: النص يجب أن يكون اسم المستخدم وليس إيموجي"""
            safe = (name or str(uid)).replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            return f'<a href="tg://user?id={uid}">{safe}</a>'

        def _chunk_mentions(mentions: list[str], per_msg: int = 50) -> list[str]:
            """تقسيم المنشنات إلى رسائل بحد أقصى per_msg منشن لكل رسالة"""
            chunks = []
            for i in range(0, len(mentions), per_msg):
                chunks.append("  ".join(mentions[i:i + per_msg]))
            return chunks

        # ── جمع رتب DB مع الاسم ──
        def _get_rank_users(rank: str) -> dict[int, str]:
            """إرجاع {user_id: first_name} من جدول ranks"""
            with _db_lock:
                conn = get_db()
                rows = conn.execute(
                    "SELECT r.user_id, COALESCE(u.first_name, '') "
                    "FROM ranks r LEFT JOIN users u "
                    "ON r.user_id = u.user_id AND r.group_id = u.group_id "
                    "WHERE r.group_id=? AND r.rank=?",
                    (group_id, rank)
                ).fetchall()
                conn.close()
            return {row[0]: row[1] or str(row[0]) for row in rows}

        vip_users     = _get_rank_users("مميز")   # {id: name}
        admin_users   = _get_rank_users("ادمن")
        manager_users = _get_rank_users("مدير")

        # ── جمع مشرفي تيليغرام الرسميين مع أسمائهم ──
        tg_admin_users: dict[int, str] = {}
        try:
            async for member in client.get_chat_members(
                group_id, filter=ChatMembersFilter.ADMINISTRATORS
            ):
                if not member.user.is_bot:
                    tg_admin_users[member.user.id] = member.user.first_name or str(member.user.id)
        except Exception as e:
            import logging
            logging.warning(f"فشل جلب مشرفي تيليغرام: {e}")

        # الـ IDs المستبعدة من قائمة الأعضاء العاديين
        excluded_ids = (
            set(vip_users) | set(admin_users) | set(manager_users) | set(tg_admin_users)
        )

        # ── إرسال منشن المميزين ──
        if vip_users:
            mentions = [_make_mention(uid, n) for uid, n in vip_users.items()]
            for chunk in _chunk_mentions(mentions):
                await message.reply_text(
                    f"⭐ <b>المميزين:</b>\n━━━━━━━━━━━━━━━━━━\n{chunk}",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )

        # ── إرسال منشن الأدمنية ──
        if admin_users:
            mentions = [_make_mention(uid, n) for uid, n in admin_users.items()]
            for chunk in _chunk_mentions(mentions):
                await message.reply_text(
                    f"⚙️ <b>الأدمنية:</b>\n━━━━━━━━━━━━━━━━━━\n{chunk}",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )

        # ── إرسال منشن المدراء ──
        if manager_users:
            mentions = [_make_mention(uid, n) for uid, n in manager_users.items()]
            for chunk in _chunk_mentions(mentions):
                await message.reply_text(
                    f"👔 <b>المدراء:</b>\n━━━━━━━━━━━━━━━━━━\n{chunk}",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )

        # ── جمع 200 عضو عادي عشوائي مع أسمائهم ──
        normal_members: list[tuple[int, str]] = []
        try:
            async for member in client.get_chat_members(group_id):
                u = member.user
                if u.is_bot or u.id in excluded_ids:
                    continue
                normal_members.append((u.id, u.first_name or str(u.id)))
        except Exception as e:
            import logging
            logging.warning(f"فشل جلب الأعضاء العاديين: {e}")

        if normal_members:
            random.shuffle(normal_members)
            selected = normal_members[:200]
            mentions = [_make_mention(uid, n) for uid, n in selected]
            for chunk in _chunk_mentions(mentions):
                await message.reply_text(
                    f"👤 <b>الأعضاء ({len(selected)}):</b>\n━━━━━━━━━━━━━━━━━━\n{chunk}",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
        elif not any([vip_users, admin_users, manager_users]):
            await message.reply_text("⚠️ لا يوجد أعضاء للمنشن.")
            return
        return

    # ================== أوامر الألعاب ==================
    if cmd_first == "لغز":   await game_quiz_start(client, message);          return
    if cmd_first == "كازينو": await game_casino(client, message, words);       return
    if cmd_first == "تحدي":  await game_duel_start(client, message, words);    return
    if cmd_first == "كرة":   await game_kora(client, message, words);          return
    if cmd_first == "سباق":  await game_race_start(client, message);           return
    if cmd_first == "وصلة":  await game_waslah_start(client, message);         return

    if t_lower in ["انهاء وصلة", "إنهاء وصلة", "وقف وصلة", "ايقاف وصلة"]:
        g = group_games.get(group_id, {})
        if g.get('waslah', {}).get('active'):
            total = len(g['waslah'].get('used', set())) - 1
            g['waslah'] = {}
            await message.reply_text(
                f"🔗 انتهت الوصلة! مجموع الكلمات: <b>{total}</b>", parse_mode=ParseMode.HTML
            )
        else:
            r = await message.reply_text("⚠️ لا توجد وصلة نشطة الآن.")
            asyncio.create_task(auto_cleanup(client, group_id, message.id, r.id))
        return
    if cmd_first == "مثل": await game_mathal_start(client, message); return
    if cmd_first in ["xo", "اكس", "اكسو", "إكس", "إكسو"]:
        await game_xo_start(client, message); return

    # الهمسة
    if cmd_first in ["هم", "همسة", "همسه", "همس", "whs"]:
        await cmd_whisper(client, message); return

    # فحص الألعاب النصية
    if await game_race_check(client, message):   return
    if await game_mathal_check(client, message): return
    if await game_waslah_check(client, message): return

    # ================== تشغيل الردود المخصصة ==================
    # 1) فحص إذا كان نص الرسالة يحتوي على اسم رد مُشغِّل
    #    (يدعم الأسماء المكوّنة من كلمة أو أكثر مثل: "حجي گلگلة")
    all_replies = db_get_all_replies()
    for rep in all_replies:
        trigger = rep['username']
        if not trigger:
            continue
        if trigger.lower() in text.lower():
            await _fire_custom_reply(
                message, client,
                rep['user_id'], rep['tg_username'] or trigger,
                rep['reply_text'], rep['media_type'], rep['media_file_id'],
            )
            return

    # 2) إذا ذكر أحدهم @شخص معروف ولديه رد → أرسل الرد أيضاً
    if message.entities:
        for entity in message.entities:
            target_id = None
            if entity.type == MessageEntityType.TEXT_MENTION and entity.user:
                target_id = entity.user.id
            elif entity.type == MessageEntityType.MENTION:
                uname_raw = _extract_entity_text(message.text, entity).lstrip('@')
                if uname_raw:
                    try:
                        tgt = await client.get_users(uname_raw)
                        target_id = tgt.id
                    except Exception:
                        continue
            if target_id:
                rep = db_get_reply(target_id)
                if rep:
                    t_trigger, t_rtext, t_tg_uname, t_mtype, t_mfid = rep
                    await _fire_custom_reply(
                        message, client,
                        target_id, t_tg_uname or t_trigger,
                        t_rtext, t_mtype, t_mfid,
                    )
                    return

    # تحديث إحصائيات المستخدم
    db_get_user(user_id, group_id, fname)
    # حفظ اسم المجموعة تلقائياً
    try:
        _gtitle = message.chat.title or ""
        with _db_lock:
            _conn = get_db()
            _conn.execute(
                "UPDATE group_settings SET group_title=? WHERE group_id=?",
                (_gtitle, str(group_id))
            )
            _conn.commit()
            _conn.close()
    except Exception:
        pass
    with _db_lock:
        conn = get_db()
        conn.execute(
            "UPDATE users SET message_count=message_count+1, xp=xp+1, first_name=? "
            "WHERE user_id=? AND group_id=?",
            (fname, user_id, group_id)
        )
        cnt = conn.execute(
            "SELECT message_count FROM users WHERE user_id=? AND group_id=?",
            (user_id, group_id)
        ).fetchone()
        if cnt and cnt[0] >= 100:
            conn.execute(
                "UPDATE users SET coins=coins+1, message_count=0 WHERE user_id=? AND group_id=?",
                (user_id, group_id)
            )
            conn.commit(); conn.close()
            try: await client.send_message(user_id, "🎉 مبروك! تجاوزت 100 رسالة وربحت عملة.")
            except: pass
        else:
            conn.commit(); conn.close()


# =========================================================
# معالج الوسائط (صور / فيديوهات / انيميشن) للمرحلة 3
# يُفعَّل عندما يُرسل الأدمن صورة أو فيديو كمحتوى للرد
# =========================================================
@app.on_message(
    (filters.photo | filters.video | filters.animation)
    & filters.group & ~filters.bot
)
async def handle_media_reply_stage(client: Client, message: Message):
    if not message.from_user:
        return
    user_id  = message.from_user.id
    group_id = message.chat.id

    pending = pending_replies.get(user_id)
    if not pending or pending.get('group_id') != group_id:
        await message.continue_propagation()
        return
    if pending.get('stage') != 3:
        await message.continue_propagation()
        return

    if 'req_msg_id' in pending:
        try: await client.delete_messages(group_id, pending['req_msg_id'])
        except: pass

    # تحديد نوع الوسيط وfile_id
    if message.photo:
        media_type   = "photo"
        media_file_id = message.photo.file_id
    elif message.video:
        media_type   = "video"
        media_file_id = message.video.file_id
    elif message.animation:
        media_type   = "animation"
        media_file_id = message.animation.file_id
    else:
        # ليس جلسة رد مخصص — نسمح للمعالجات اللاحقة بالتنفيذ
        await message.continue_propagation()
        return

    reply_text = (message.caption or "").strip()

    db_add_reply(
        pending['target_user_id'],
        pending['trigger_name'],
        reply_text,
        pending['target_tg_username'],
        media_type,
        media_file_id,
    )

    media_label = {"photo": "صورة 🖼", "video": "فيديو 🎬", "animation": "GIF 🎞"}.get(media_type, "وسيط")
    preview = reply_text[:40] + ('...' if len(reply_text) > 40 else '') if reply_text else "—"
    await message.reply_text(
        f"✅ <b>تم حفظ الرد بنجاح!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 الشخص: {pending['target_display']}\n"
        f"🔑 الاسم المُشغِّل: <b>{pending['trigger_name']}</b>\n"
        f"📎 النوع: {media_label}\n"
        f"💬 التعليق: {preview}",
        parse_mode=ParseMode.HTML
    )
    pending_replies.pop(user_id, None)


# ══════════════════════════════════════════════════════════════
#  معالج الميديا التلقائي — حذف دُفعي بعد 5 دقائق
#
#  الإصلاحات المُطبَّقة:
#  1) group=1  → يعمل مستقلاً عن handle_media_reply_stage
#               (يشمل ميديا المشرفين حتى في وضع إضافة الردود)
#  2) دُفعي   → تُجمَّع كل الوسائط في نافذة 5 دقائق ثم تُحذف دفعةً واحدة
#  3) مرجع قوي → _active_delete_tasks يمنع Python (GC) من إلغاء المؤقت
#  4) إشعار   → يُرسَل بعد الحذف مع عدد الوسائط المحذوفة
# ══════════════════════════════════════════════════════════════

@app.on_message(
    filters.group
    & ~filters.bot
    & (filters.photo | filters.video | filters.sticker | filters.animation),
    group=1   # ← مجموعة منفصلة: يُنفَّذ دائماً بغض النظر عن المعالجات الأخرى
)
async def handle_media_auto_delete(client: Client, message: Message):
    """
    إذا كان auto_delete_media مفعّلاً في المجموعة:
    • تُجمَّع الصور / المقاطع / الملصقات / المتحركات (من الأعضاء والمشرفين)
    • بعد 5 دقائق تُحذف الدُفعة كلها دفعةً واحدة
    • تُستثنى الرسالة المثبّتة
    • يُرسَل إشعار بعدد الوسائط المحذوفة
    """
    group_id = message.chat.id
    settings = db_get_settings(str(group_id))
    if not settings.get('auto_delete_media', 0):
        return

    # ── أضف معرّف الرسالة لقائمة انتظار المجموعة ──
    batch = _auto_delete_batches.setdefault(group_id, {'ids': [], 'task': None})
    batch['ids'].append(message.id)

    # ── إذا لم يكن هناك مؤقت نشط → أنشئ واحداً ──
    if batch['task'] is None or batch['task'].done():

        async def _batch_delete():
            await asyncio.sleep(300)   # ← 5 دقائق حقيقية

            b          = _auto_delete_batches.get(group_id, {})
            ids_to_del = list(b.get('ids', []))
            b['ids']   = []     # أعد ضبط القائمة للدورة القادمة
            b['task']  = None

            if not ids_to_del:
                return

            # ── استثناء الرسالة المثبّتة ──
            try:
                chat = await client.get_chat(group_id)
                if chat.pinned_message and chat.pinned_message.id in ids_to_del:
                    ids_to_del.remove(chat.pinned_message.id)
            except Exception:
                pass

            count = len(ids_to_del)
            if count == 0:
                return

            # ── حذف الرسائل (بحد أقصى 100 في كل طلب) ──
            for i in range(0, len(ids_to_del), 100):
                try:
                    await client.delete_messages(group_id, ids_to_del[i:i + 100])
                except Exception:
                    pass

            # ── إشعار ما بعد الحذف ──
            try:
                if count == 1:
                    summary = "وسيط واحد"
                elif count == 2:
                    summary = "وسيطين"
                elif 3 <= count <= 10:
                    summary = f"{count} وسائط"
                else:
                    summary = f"{count} وسيطاً"

                notif = await client.send_message(
                    group_id,
                    f"🗑️ <b>الحذف التلقائي</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"✅ تم حذف <b>{summary}</b> تلقائياً\n"
                    f"⏱ أُرسلت خلال آخر 5 دقائق\n"
                    f"<i>(📸 صور • 🎬 فيديو • 🎭 ملصقات • ✨ GIF)</i>",
                    parse_mode=ParseMode.HTML,
                )
                # احذف الإشعار بعد 30 ثانية
                async def _del_notif():
                    await asyncio.sleep(30)
                    try:
                        await client.delete_messages(group_id, notif.id)
                    except Exception:
                        pass
                notif_task = asyncio.create_task(_del_notif())
                _active_delete_tasks.add(notif_task)
                notif_task.add_done_callback(_active_delete_tasks.discard)
            except Exception:
                pass

        # ── إنشاء المؤقت مع مرجع قوي لمنع GC ──
        task = asyncio.create_task(_batch_delete())
        batch['task'] = task
        _active_delete_tasks.add(task)                    # ← يمنع حذف المؤقت
        task.add_done_callback(_active_delete_tasks.discard)  # ← تنظيف تلقائي

# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    init_db()
    insert_trivia()
    print("\U0001F680 بوت ذكي يعمل الآن...")
    app.run()


if __name__ == '__main__':
    main()
