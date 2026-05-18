#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.py — config | games_data | database | guard | state
"""

# ╔══════════════════════════════════════════════════════════╗
# ║                        CONFIG                           ║
# ╚══════════════════════════════════════════════════════════╝

BOT_TOKEN    = "8791479511:AAE8OIzyFb5C88LHdSI6jDjG_3upf4dVSXM"
API_ID       = 30467527
API_HASH     = "08649a73985066271ac30dc103d15f92"
BOT_USERNAME = "BoootGPT_bot"
OWNER_ID     = 1376810531
DB_PATH      = "zeky.db"
CHANNEL_ID   = "@ra7eel17"

AI_API_KEY   = "lfu_cxPmpxH_qmt-5Dg0kMzGlzG3cv9Sc_QO"

BIO_COMMANDS     = ["بايو", "نبذة", "نبذه", "نبذتي", "bio"]
PROFILE_COMMANDS = ["ا", "ايدي", "id", "الايدي", "أ", "إيدي", "myid"]

WELCOME_MESSAGES = [
    "🌟 أهلاً وسهلاً {mention}، نورت المجموعة! يالله تفاعل وشاركنا.",
    "🎉 هلا وغلا {mention}، انضميت لأفضل مجموعة! حياك الله.",
    "🤩 وصل الغالي {mention}، منور الحضور والله!",
    "💫 أهلاً {mention}، نورتنا وزدتنا شرف! تفضل وشارك.",
    "🎊 مرحباً {mention}، أسعدتنا بوجودك! انضم للتفاعل.",
    "⚡️ هلا {mention}، وجودك يفرق! تفضل وحط بصمتك.",
    "🔥 دخل الأسطورة {mention}، حياك الله بين إخوانك!",
    "💎 أهلاً بالغالي {mention}، نورت المجموعة!",
    "🚀 هلا {mention}، انضميت للكوكبة! يالله نبدع.",
    "🌸 مرحباً {mention}، أسعد الله أوقاتك! حياك.",
]

BAD_WORDS = [
    "كس","كسك","كسمك","كسختك","كسخت","كسم","كسخ","كس امك","كس اختك","كس ختك",
    "زب","زبي","زبك","زبه","زبرها","زبر","زبور","قضيب","أير","اير","أيري","عير","عيري",
    "طيز","طيزك","طيزه","طيزج","طيزي","طيزها","طيزو","طيز امك","طيز اختك","شرج",
    "بظر","فرج","خصيتك","خصيتي","خصيان","خصوة","خصاوي",
    "نيك","نيج","نياك","متناك","متناكة","منيوك","منيوكة","منيج","ناك","ينيك","انيك","اناج","نايج","ناكها",
    "لحس","لعق","مص","تمص","اغتصاب",
    "شرموط","شرموطة","شراميط","شرموطات","قحبة","قحاب","قحب","قحباء",
    "عاهرة","عاهرات","زانية","زاني","زناة",
    "ديوث","ديوثة","ديايث",
    "لوطي","لوطية","لواط","مأبون","مأبونة","خول","خولات","خوال","خوله","خولية",
    "سحاق","سحاقية","خنثي","خنيث",
    "ابن الشرموطة","ابن القحبة","ابن المتناكة","ابن المنيوكة","أخو الشرموطة",
]


# ╔══════════════════════════════════════════════════════════╗
# ║                      GAMES DATA                         ║
# ╚══════════════════════════════════════════════════════════╝

AMTHAL = [
    ("من شبّ على شيء",        "شاب عليه"),
    ("الصديق وقت",            "الضيق"),
    ("اليد الواحدة",           "لا تصفق"),
    ("اضرب حديدة",            "وهي حامية"),
    ("خير الكلام",             "ما قلّ ودلّ"),
    ("العين بصيرة",           "واليد قصيرة"),
    ("من جدّ وجد",            "ومن زرع حصد"),
    ("حبل الكذب",              "قصير"),
    ("العجلة من",              "الشيطان"),
    ("الغائب",                 "حجّته معه"),
    ("من يزرع الشوك",         "لا يحصد العنب"),
    ("القرد في عين أمه",       "غزال"),
    ("الجار قبل",              "الدار"),
    ("كلّ وعاء يرشح",         "بما فيه"),
    ("العقل زينة",             "والأدب زيادة"),
    ("اللي ما له أول",         "ما له آخر"),
    ("اللسان",                 "ميزان الإنسان"),
    ("صاحب الحظ",              "تجيه الأرانب وهو نايم"),
    ("خذ القرار",              "ولا تحتار"),
    ("كلام الليل",             "يمحوه النهار"),
    ("من أمن العقوبة",         "أساء الأدب"),
    ("اطلب العلم",             "من المهد إلى اللحد"),
    ("الوقت",                  "كالسيف إن لم تقطعه قطعك"),
    ("العلم في الصغر",         "كالنقش في الحجر"),
    ("اتق شر من",              "أحسنت إليه"),
]

HAQEEBA = [
    ("🎉 ربحت عملة ذهبية!",         "coins", +1),
    ("💸 خسرت عملة! حظك مع القادمة.", "coins", -1),
    ("⭐ ربحت 10 نقاط XP!",           "xp",    +10),
    ("🎁 مزدوج! ربحت عملتين!",        "coins", +2),
    ("😴 الحقيبة فارغة! حظاً أوفر.",  None,    0),
    ("🍀 حظك عظيم! +3 عملات!",        "coins", +3),
    ("💀 الحقيبة الملعونة! -2 عملة.", "coins", -2),
    ("🌟 نجمة حظ! +15 نقطة XP",       "xp",    +15),
    ("🎰 ربحت 5 عملات!",              "coins", +5),
    ("🃏 بطاقة خاسرة! لا شيء.",       None,    0),
]

QUIZ_DATA = [
    {"q": "عاصمة المملكة العربية السعودية؟",       "opts": ["الرياض","جدة","مكة المكرمة","الدمام"],          "ans": 0},
    {"q": "من اخترع الهاتف؟",                      "opts": ["ماركوني","إديسون","غراهام بيل","نيوتن"],         "ans": 2},
    {"q": "كم عدد الدول العربية؟",                  "opts": ["18","20","22","25"],                             "ans": 2},
    {"q": "أطول نهر في العالم؟",                   "opts": ["الأمازون","النيل","الفرات","الكونغو"],            "ans": 1},
    {"q": "مؤسس علم الجبر؟",                       "opts": ["ابن سينا","الخوارزمي","الفارابي","البيروني"],    "ans": 1},
    {"q": "أكبر دولة في العالم مساحةً؟",            "opts": ["كندا","روسيا","الصين","أمريكا"],                "ans": 1},
    {"q": "عاصمة فرنسا؟",                         "opts": ["برلين","روما","مدريد","باريس"],                 "ans": 3},
    {"q": "الكوكب الأحمر؟",                        "opts": ["الزهرة","المشتري","المريخ","زحل"],               "ans": 2},
    {"q": "كم عدد أيام السنة الكبيسة؟",             "opts": ["364","365","366","367"],                         "ans": 2},
    {"q": "عاصمة تركيا؟",                          "opts": ["إسطنبول","أنقرة","إزمير","بورصة"],              "ans": 1},
    {"q": "من اخترع المصباح الكهربائي؟",             "opts": ["إديسون","نيوتن","فاراداي","تسلا"],              "ans": 0},
    {"q": "أصغر كوكب في المجموعة الشمسية؟",         "opts": ["عطارد","المريخ","الأرض","نبتون"],               "ans": 0},
    {"q": "عاصمة اليابان؟",                        "opts": ["سيول","بكين","طوكيو","أوساكا"],                 "ans": 2},
    {"q": "أكبر قارة في العالم؟",                  "opts": ["أفريقيا","أمريكا","آسيا","أوروبا"],             "ans": 2},
    {"q": "ما عاصمة البرازيل؟",                    "opts": ["ساو باولو","ريو دي جانيرو","برازيليا","بيلو هوريزونتي"], "ans": 2},
    {"q": "أسرع حيوان بري؟",                       "opts": ["الأسد","النمر","الفهد","الحصان"],               "ans": 2},
    {"q": "من كتب روايات هاري بوتر؟",               "opts": ["ستيفن كينغ","ج.ك. رولينغ","تولكين","دوستويفسكي"],"ans": 1},
    {"q": "كم يوماً يستغرق دوران القمر حول الأرض؟", "opts": ["7 أيام","14 يوماً","27 يوماً","365 يوماً"],      "ans": 2},
    {"q": "ما رمز الذهب الكيميائي؟",               "opts": ["Go","Gd","Au","Ag"],                            "ans": 2},
    {"q": "أي دولة تملك أكبر احتياطي نفطي؟",       "opts": ["روسيا","الكويت","السعودية","فنزويلا"],           "ans": 3},
]

RACE_PHRASES = [
    "القرآن الكريم نور وهدى للناس",
    "الأخلاق الحسنة تاج على رأس صاحبها",
    "من صبر ظفر بما أراد",
    "العلم نور والجهل ظلام",
    "الوقت كالسيف إن لم تقطعه قطعك",
    "طالب العلم في سبيل الله",
    "الصدق ينجي والكذب يهلك",
    "المعلم رسالة ومسؤولية عظيمة",
    "الصبر مفتاح الفرج والنجاح",
    "من جد وجد ومن زرع حصد",
]


# ╔══════════════════════════════════════════════════════════╗
# ║                      DATABASE                           ║
# ╚══════════════════════════════════════════════════════════╝

import sqlite3
import threading
from datetime import datetime

_db_lock = threading.Lock()


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _db_lock:
        conn = get_db()
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER, group_id INTEGER, first_name TEXT DEFAULT '',
                      coins INTEGER DEFAULT 3, first_seen TEXT,
                      message_count INTEGER DEFAULT 0, xp INTEGER DEFAULT 0,
                      rank TEXT DEFAULT 'عضو', PRIMARY KEY (user_id, group_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS trivia_questions
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, answer TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS streaks
                     (user_id INTEGER, group_id INTEGER, streak INTEGER DEFAULT 0,
                      PRIMARY KEY (user_id, group_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS group_settings
                     (group_id TEXT PRIMARY KEY, filter_bad_words INTEGER DEFAULT 1)''')
        c.execute('''CREATE TABLE IF NOT EXISTS ranks
                     (user_id INTEGER, group_id INTEGER, rank TEXT DEFAULT 'عضو',
                      PRIMARY KEY (user_id, group_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS muted_users
                     (user_id INTEGER, group_id INTEGER, mute_until TEXT DEFAULT NULL,
                      PRIMARY KEY (user_id, group_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS warnings
                     (user_id INTEGER, group_id INTEGER, count INTEGER DEFAULT 0,
                      PRIMARY KEY (user_id, group_id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS punishments
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                      group_id INTEGER, admin_id INTEGER,
                      action TEXT, timestamp TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS custom_replies
                     (user_id INTEGER PRIMARY KEY, username TEXT, reply_text TEXT)''')
        for _col, _def in [
            ("tg_username",   "TEXT DEFAULT ''"),
            ("media_type",    "TEXT DEFAULT ''"),
            ("media_file_id", "TEXT DEFAULT ''"),
        ]:
            try:
                c.execute(f"ALTER TABLE custom_replies ADD COLUMN {_col} {_def}")
            except sqlite3.OperationalError:
                pass
        extra_cols = {
            'lock_foreign':    'INTEGER DEFAULT 0',
            'lock_links':      'INTEGER DEFAULT 0',
            'lock_cliche':     'INTEGER DEFAULT 0',
            'lock_forward':    'INTEGER DEFAULT 0',
            'lock_usernames':  'INTEGER DEFAULT 0',
            'lock_flood':      'INTEGER DEFAULT 0',
            'photo_profile':   'INTEGER DEFAULT 1',
            'slow_mode':       'INTEGER DEFAULT 0',
            'whisper_enabled': 'INTEGER DEFAULT 1',
            'ndaa_enabled':    'INTEGER DEFAULT 1',
            'auto_delete_media': 'INTEGER DEFAULT 0',
            'group_title':     'TEXT DEFAULT ""',
        }
        for col, dtype in extra_cols.items():
            try:
                c.execute(f"ALTER TABLE group_settings ADD COLUMN {col} {dtype}")
            except sqlite3.OperationalError:
                pass
        try:
            c.execute("ALTER TABLE users ADD COLUMN first_name TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        c.execute('''CREATE TABLE IF NOT EXISTS audio_cache
                     (query TEXT PRIMARY KEY, file_id TEXT, title TEXT,
                      created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()


def insert_trivia():
    with _db_lock:
        conn = get_db()
        c = conn.cursor()
        if c.execute("SELECT COUNT(*) FROM trivia_questions").fetchone()[0] == 0:
            c.executemany("INSERT INTO trivia_questions (question, answer) VALUES (?, ?)", [
                ("عاصمة العراق؟",       "بغداد"),
                ("عاصمة مصر؟",          "القاهرة"),
                ("مؤسس علم الجبر؟",     "الخوارزمي"),
                ("عاصمة فرنسا؟",        "باريس"),
                ("الكوكب الأحمر؟",      "المريخ"),
                ("عاصمة السعودية؟",     "الرياض"),
                ("النبي الذي ابتلعه الحوت؟", "يونس"),
                ("عدد الدول العربية؟",  "22"),
            ])
            conn.commit()
        conn.close()



def db_audio_cache_get(query: str):
    """يرجع (file_id, title) إذا موجود في الكاش، وإلا None."""
    with _db_lock:
        conn = get_db()
        row = conn.execute(
            "SELECT file_id, title FROM audio_cache WHERE query = ?",
            (query.lower().strip(),)
        ).fetchone()
        conn.close()
    return (row[0], row[1]) if row else None


def db_audio_cache_set(query: str, file_id: str, title: str):
    """يحفظ file_id في الكاش."""
    with _db_lock:
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO audio_cache (query, file_id, title) VALUES (?, ?, ?)",
            (query.lower().strip(), file_id, title)
        )
        conn.commit()
        conn.close()


def db_get_user(user_id, group_id, first_name=""):
    with _db_lock:
        conn = get_db()
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, group_id, first_name, first_seen) VALUES (?, ?, ?, ?)",
            (user_id, group_id, first_name, datetime.now().isoformat())
        )
        if first_name:
            conn.execute(
                "UPDATE users SET first_name=? WHERE user_id=? AND group_id=? "
                "AND (first_name='' OR first_name IS NULL)",
                (first_name, user_id, group_id)
            )
        row = conn.execute(
            "SELECT coins, message_count, xp FROM users WHERE user_id=? AND group_id=?",
            (user_id, group_id)
        ).fetchone()
        conn.commit()
        conn.close()
        return (row[0], row[1], row[2]) if row else (3, 0, 0)


def db_get_settings(group_id: str):
    with _db_lock:
        conn = get_db()
        conn.execute("INSERT OR IGNORE INTO group_settings (group_id) VALUES (?)", (group_id,))
        row = conn.execute(
            "SELECT filter_bad_words, lock_foreign, lock_links, lock_cliche, lock_forward, "
            "lock_usernames, lock_flood, photo_profile, slow_mode, whisper_enabled, ndaa_enabled, "
            "auto_delete_media FROM group_settings WHERE group_id=?", (group_id,)
        ).fetchone()
        conn.commit()
        conn.close()
        return {
            'bad_words': row[0], 'foreign': row[1], 'links': row[2],
            'cliche': row[3], 'forward': row[4], 'usernames': row[5],
            'flood': row[6], 'photo': row[7], 'slow': row[8],
            'whisper': row[9] if row[9] is not None else 1,
            'ndaa': row[10] if row[10] is not None else 1,
            'auto_delete_media': row[11] if row[11] is not None else 0,
        }


def db_set_setting(group_id: str, column: str, value: int):
    with _db_lock:
        conn = get_db()
        conn.execute(f"UPDATE group_settings SET {column}=? WHERE group_id=?", (value, group_id))
        conn.commit()
        conn.close()


def db_get_streak(user_id, group_id):
    with _db_lock:
        conn = get_db()
        conn.execute("INSERT OR IGNORE INTO streaks (user_id, group_id) VALUES (?, ?)", (user_id, group_id))
        s = conn.execute(
            "SELECT streak FROM streaks WHERE user_id=? AND group_id=?", (user_id, group_id)
        ).fetchone()[0]
        conn.commit()
        conn.close()
        return s


def db_add_mute(user_id, group_id, until_iso=None):
    with _db_lock:
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO muted_users (user_id, group_id, mute_until) VALUES (?, ?, ?)",
            (user_id, group_id, until_iso)
        )
        conn.commit()
        conn.close()


def db_remove_mute(user_id, group_id):
    with _db_lock:
        conn = get_db()
        conn.execute("DELETE FROM muted_users WHERE user_id=? AND group_id=?", (user_id, group_id))
        conn.commit()
        conn.close()


def db_get_muted(group_id):
    with _db_lock:
        conn = get_db()
        rows = conn.execute(
            "SELECT user_id FROM muted_users WHERE group_id=?", (group_id,)
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]


def db_add_warning(user_id, group_id) -> int:
    with _db_lock:
        conn = get_db()
        conn.execute("INSERT OR IGNORE INTO warnings (user_id, group_id) VALUES (?, ?)", (user_id, group_id))
        conn.execute("UPDATE warnings SET count=count+1 WHERE user_id=? AND group_id=?", (user_id, group_id))
        count = conn.execute(
            "SELECT count FROM warnings WHERE user_id=? AND group_id=?", (user_id, group_id)
        ).fetchone()[0]
        conn.commit()
        conn.close()
        return count


def db_clear_warnings(user_id, group_id):
    with _db_lock:
        conn = get_db()
        conn.execute("UPDATE warnings SET count=0 WHERE user_id=? AND group_id=?", (user_id, group_id))
        conn.commit()
        conn.close()


def db_get_warnings(user_id, group_id) -> int:
    with _db_lock:
        conn = get_db()
        row = conn.execute(
            "SELECT count FROM warnings WHERE user_id=? AND group_id=?", (user_id, group_id)
        ).fetchone()
        conn.close()
        return row[0] if row else 0


def db_log_punishment(user_id, group_id, admin_id, action):
    with _db_lock:
        conn = get_db()
        conn.execute(
            "INSERT INTO punishments (user_id, group_id, admin_id, action, timestamp) VALUES (?, ?, ?, ?, ?)",
            (user_id, group_id, admin_id, action, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
        conn.close()


def db_get_punishments(user_id, group_id, limit=10):
    with _db_lock:
        conn = get_db()
        rows = conn.execute(
            "SELECT action, timestamp FROM punishments "
            "WHERE user_id=? AND group_id=? ORDER BY id DESC LIMIT ?",
            (user_id, group_id, limit)
        ).fetchall()
        conn.close()
        return rows


def db_get_rank(user_id, group_id):
    with _db_lock:
        conn = get_db()
        row = conn.execute(
            "SELECT rank FROM ranks WHERE user_id=? AND group_id=?", (user_id, group_id)
        ).fetchone()
        conn.close()
        return row[0] if row else 'عضو'


def db_add_reply(user_id, trigger_name, reply_text, tg_username="", media_type="", media_file_id=""):
    with _db_lock:
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO custom_replies "
            "(user_id, username, reply_text, tg_username, media_type, media_file_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, trigger_name, reply_text, tg_username, media_type, media_file_id)
        )
        conn.commit()
        conn.close()


def db_get_reply(user_id):
    with _db_lock:
        conn = get_db()
        row = conn.execute(
            "SELECT username, reply_text, tg_username, media_type, media_file_id "
            "FROM custom_replies WHERE user_id=?", (user_id,)
        ).fetchone()
        conn.close()
        if row:
            return (row['username'], row['reply_text'], row['tg_username'],
                    row['media_type'], row['media_file_id'])
        return None


def db_get_all_replies():
    with _db_lock:
        conn = get_db()
        rows = conn.execute(
            "SELECT user_id, username, reply_text, tg_username, media_type, media_file_id "
            "FROM custom_replies ORDER BY username"
        ).fetchall()
        conn.close()
        return [
            {'user_id': r['user_id'], 'username': r['username'], 'reply_text': r['reply_text'],
             'tg_username': r['tg_username'], 'media_type': r['media_type'], 'media_file_id': r['media_file_id']}
            for r in rows
        ]


def db_delete_reply(user_id):
    with _db_lock:
        conn = get_db()
        conn.execute("DELETE FROM custom_replies WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()


def db_find_reply_by_name(name: str):
    with _db_lock:
        conn = get_db()
        row = conn.execute(
            "SELECT user_id, username, reply_text, tg_username, media_type, media_file_id "
            "FROM custom_replies WHERE LOWER(username) = LOWER(?)", (name,)
        ).fetchone()
        conn.close()
        if row:
            return (row['user_id'], row['username'], row['reply_text'],
                    row['tg_username'], row['media_type'], row['media_file_id'])
    return None


# ╔══════════════════════════════════════════════════════════╗
# ║                       GUARD                             ║
# ╚══════════════════════════════════════════════════════════╝

import re


class ContentGuard:
    def __init__(self, bad_words):
        self.bad_words     = set(bad_words)
        self.nuclear_words = {"كسم","منيوك","قحبه","قحبة","طيز","نيك","شرموط","زب","كس","خول","سحاق"}
        self.whitelist     = {"كسكسي","ماركوس","مناكير","تونس","هواك","تصدر","يصدر","مصدر","إصدار","اصدار","مجتمع","جماعة","اجتماع"}
        self.arabish_map   = {
            '3':'ع','7':'ح','5':'خ','8':'ق','9':'ص','2':'ء','6':'ط','4':'غ',
            'a':'ا','b':'ب','d':'د','e':'ي','f':'ف','h':'ه','i':'ي','j':'ج',
            'k':'ك','l':'ل','m':'م','n':'ن','o':'و','p':'ب','q':'ق','r':'ر',
            's':'س','t':'ت','w':'و','y':'ي','z':'ز',
        }
        self.arabish_multi = {'sh':'ش','kh':'خ','gh':'غ','th':'ث','dh':'ذ','ch':'ش'}
        self.arabish_dict  = {
            'tyz','tiz','teez','ks','kas','kos','kus','zb','nik','ni3k','neek',
            'shr8t','shrm8t','q7ba','q7bh','kahba','qahba','mnywk','mniwk','manyok',
        }
        self.safe_words = {
            "كسر","كسرت","كسرنا","كسروا","مكسور","ينكسر","انكسر","كسور","تكسير",
            "كسل","كسول","كسلان","كسالى","كسوف","كسوة","كساء","كسير","عسكر",
            "عسكري","عساكر","معسكر","إكسير","كسكسي","ماركوس","مكسيك","تكساس",
            "كلاسيك","تصدر","يصدر","مصدر","إصدار","اصدار","مجتمع","جماعة","اجتماع",
        }
        self.split_pattern = re.compile(
            r'[\U00010000-\U0010ffff\u2600-\u27BF\u2300-\u23FF\uFE00-\uFE0F'
            r'\u200B-\u200F\uFEFF\.,،_\-\*\+\=\|\/\\~`^@#$%&!]',
            re.UNICODE
        )

    def _apply_arabish(self, text):
        for eng, arb in self.arabish_multi.items():
            text = text.replace(eng, arb)
        for eng, arb in self.arabish_map.items():
            text = text.replace(eng, arb)
        return text

    def _normalize(self, text):
        if not text: return ""
        text = text.lower()
        text = self.split_pattern.sub('', text)
        text = re.sub(r'[\u0617-\u061A\u064B-\u0652]', '', text)
        text = self._apply_arabish(text)
        text = re.sub(r'[أإآ]', 'ا', text)
        text = re.sub(r'ة', 'ه', text)
        return re.sub(r'(.)\1+', r'\1', text)

    def _check_arabish_dict(self, word):
        return re.sub(r'[^a-z0-9]', '', word.lower()) in self.arabish_dict

    def is_profane(self, original_text):
        if not original_text: return False
        normalized = self._normalize(original_text)
        filtered   = ' '.join(w for w in normalized.split() if w not in self.safe_words)
        for word in filtered.split():
            if word in self.bad_words and word not in self.whitelist:
                return True
        arabic_only = re.sub(r'[^\u0621-\u064A]', '', filtered)
        for nw in self.nuclear_words:
            if nw in arabic_only and not any(w in filtered for w in self.whitelist):
                return True
        for word in original_text.lower().split():
            if self._check_arabish_dict(word):
                return True
        return False


guard = ContentGuard(BAD_WORDS)


# ╔══════════════════════════════════════════════════════════╗
# ║                       STATE                             ║
# ╚══════════════════════════════════════════════════════════╝

from pyrogram import Client

client_app = Client("bot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

_user_sessions: dict = {}
group_games:    dict = {}
WHISPERS_CACHE: dict = {}

XO_GAMES      = {}
XO_CHALLENGES = {}

flood_cache     = {}
slow_mode_cache = {}

pending_replies:        dict = {}
pending_delete_replies: dict = {}
pending_auto_tag:       dict = {}
