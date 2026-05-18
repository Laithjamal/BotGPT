# 🔐 إعداد cookies.txt لتشغيل ميزة "يوت"

## ليش أحتاج cookies؟

من 2025-2026 صار يوتيوب يحجب طلبات التنزيل من **السيرفرات السحابية** (مثل Heroku, Railway, AWS, Pterodactyl panels) ويطلب تحقق "Sign in to confirm you're not a bot".

الحل الوحيد المستقر هو تمرير ملف **cookies.txt** لـ `yt-dlp` يحتوي جلسة دخولك في يوتيوب.

---

## الخطوات (5 دقائق)

### 1. حسّب فرعي
**مهم جداً**: استخدم حساب جوجل **فرعي** (مو حسابك الأساسي) لأن يوتيوب ممكن يقفل الحساب لو شك إنه بوت.

### 2. نزّل إضافة المتصفح

اختر واحدة:

| المتصفح | الإضافة |
|---------|---------|
| Chrome / Edge | [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) |
| Firefox | [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/) |

### 3. تصدير الكوكيز

1. سجّل دخول على `youtube.com` بحسابك الفرعي
2. افتح الإضافة على نفس صفحة يوتيوب
3. اضغط **Export As Netscape format** (مهم!)
4. احفظ الملف باسم `cookies.txt`

### 4. ارفعه للسيرفر

ضع `cookies.txt` بنفس مجلد `app.py`:

```
BotGPT/
├── app.py
├── core.py
├── ai_helper.py
├── cookies.txt   ← هنا
└── requirements.txt
```

البوت يبحث تلقائياً في هاي المسارات بالترتيب:
1. `<مجلد البوت>/cookies.txt`
2. `~/cookies.txt`
3. `/root/cookies.txt`
4. `/app/cookies.txt`
5. `/home/container/cookies.txt`

### 5. أعِد تشغيل البوت

بس. ميزة "يوت" راح تشتغل فوراً.

---

## نصائح مهمة

- 🕒 الكوكيز تنتهي صلاحيتها كل ~30 يوم. لما تجي الرسالة "Sign in to confirm" مرة ثانية، صدّر ملف جديد.
- 🚫 لا تشارك ملف `cookies.txt` — هو بمثابة كلمة مرورك.
- 🔒 أضِفه لـ `.gitignore` لو ترفع المشروع على GitHub.
- ⚠️ لا تستخدم حسابك الأساسي — استخدم حساب فرعي.

---

## استكشاف الأخطاء

### "ملف cookies.txt مش متعرّف عليه"
- تأكد إن الصيغة Netscape (مو JSON)
- تأكد إن حجم الملف > 100 بايت
- تأكد إنك صدّرته من `youtube.com` نفسها

### "ما زالت الرسالة Bot Detection تطلع"
- جرّب حساب يوتيوب فرعي ثاني
- شغّل البوت من VPS بـ IP نظيف (مو AWS/GCP — استخدم Hetzner, OVH, Contabo)
- جرّب تحديث yt-dlp: `pip install -U yt-dlp`

### "يحمّل بس الجودة واطية"
- زد قيمة `max_filesize` في `_build_ydl_opts` بـ `app.py`
- استخدم كلمة "كاملة" بعد الأغنية: `يوت اسم الأغنية كاملة`
