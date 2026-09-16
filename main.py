# -*- coding: utf-8 -*-
"""
HS Code Master - Arabic Edition
Gamified HS code memorization app for customs work.
Built for Kivy / Pydroid3

FILES NEEDED IN THE SAME FOLDER:
  main.py            (this file)
  hs_codes_ar.json    (your real Syrian customs tariff data, grouped by heading)
  quotes_ar.json       (Arabic quotes shown on launch)
  quotes_en.json       (English quotes shown on launch)
  arabic_font.ttf      (OPTIONAL but recommended - see note below)

progress.json is created automatically the first time you run the app.

============================================================
IMPORTANT - READ BEFORE RUNNING (Arabic text support)
============================================================
Kivy does NOT render Arabic correctly out of the box: letters need to be
"reshaped" (connected into their correct joined forms) and reordered
right-to-left. This file handles that automatically using two extra
libraries. In Pydroid3's pip menu, install:

    arabic_reshaper
    python-bidi

The app will try to find an Arabic-capable font automatically (many
Android phones already have one system-side). If Arabic text shows up
as empty boxes, download a free font such as "Noto Naskh Arabic" or
"Amiri-Regular.ttf" and place it in this same folder, named exactly:

    arabic_font.ttf
============================================================
"""

import json
import os
import random
import re
from datetime import date

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.scrollview import ScrollView
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.graphics import Color, Rectangle
from kivy.utils import escape_markup

# ---------- Arabic text shaping ----------
try:
    from arabic_reshaper import ArabicReshaper
    from bidi.algorithm import get_display
    # support_ligatures=False avoids empty "tofu" boxes for combined
    # letter forms (like Lam-Alef) that not every font has a glyph for.
    # delete_harakat=True strips diacritic marks (tashkeel) - several
    # auto-detected system fonts are missing glyphs for these too, and
    # they aren't needed to read the descriptions.
    _reshaper = ArabicReshaper(configuration={
        "delete_harakat": True,
        "support_ligatures": False,
    })
    RESHAPE_OK = True
    RESHAPE_IMPORT_ERROR = None
except ImportError as _e:
    RESHAPE_OK = False
    _reshaper = None
    RESHAPE_IMPORT_ERROR = str(_e)


ARABIC_RANGE = re.compile(r'[\u0600-\u06FF]')

# Invisible bidi control/formatting characters. These sometimes end up
# embedded in text copied from PDFs/Word docs (e.g. the original customs
# tariff document). They are invisible but they confuse arabic_reshaper
# and python-bidi's own reordering logic, producing scrambled output on
# top of our manual reshape+reorder - so we strip them entirely.
_BIDI_CONTROL_CHARS = re.compile(
    '[\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069]'
)

# Arabic-specific punctuation that several lightweight/system Arabic
# fonts ship without a glyph for (they show up as empty "tofu" boxes
# even though the font otherwise renders Arabic letters fine). Their
# plain ASCII equivalents are visually close enough and guaranteed to
# exist in any font.
_ARABIC_PUNCT_MAP = {
    "\u061b": ";",   # ARABIC SEMICOLON ؛
    "\u060c": ",",   # ARABIC COMMA ،
    "\u061f": "?",   # ARABIC QUESTION MARK ؟
    "\u066a": "%",   # ARABIC PERCENT SIGN ٪
}

_WHITESPACE_RUN = re.compile(r'\s+')

# A parenthesis glued directly to an Arabic letter on both sides (no
# surrounding space at all, e.g. "بطاطا(بطاطس)") appears to trigger the
# same kind of shaping/mirroring corruption as the embedded-newline bug
# above - a normal-looking paren character ends up rendered as an
# unsupported glyph. Forcing a space around it sidesteps the issue
# without changing the readable meaning.
_PAREN_BEFORE_AR = re.compile(r'([\u0600-\u06FF])([({])')
_PAREN_AFTER_AR = re.compile(r'([)}])([\u0600-\u06FF])')

# Harakat (tashkeel), Quranic recitation/pause marks, and other Arabic
# combining marks. arabic_reshaper's own delete_harakat option only
# covers the basic tashkeel set - quotes containing Quranic verses or
# heavily-voweled poetry often carry extra marks (waqf signs, extended
# Arabic-Supplement marks) that regular phone fonts have no glyph for
# at all, which is why such text can render as a solid wall of boxes
# even though plain Arabic letters right next to it look fine.
_ARABIC_DIACRITICS = re.compile(
    '[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08D3-\u08FF\u0640]'
)


def clean_ar_text(text):
    """Strip invisible bidi-control characters, harakat/diacritics, and
    swap Arabic-only punctuation marks for their ASCII equivalents, so
    text renders consistently regardless of which font/glyph-set is
    available."""
    if not text:
        return text
    text = str(text)
    text = _BIDI_CONTROL_CHARS.sub("", text)
    text = _ARABIC_DIACRITICS.sub("", text)
    text = _PAREN_BEFORE_AR.sub(r'\1 \2', text)
    text = _PAREN_AFTER_AR.sub(r'\1 \2', text)
    for src, dst in _ARABIC_PUNCT_MAP.items():
        text = text.replace(src, dst)
    text = _WHITESPACE_RUN.sub(" ", text).strip()
    return text


def has_arabic(text):
    return bool(ARABIC_RANGE.search(text)) if text else False


def truncate_ar(text, max_len=110):
    """Cap very long descriptions (some real HS chapter headings run
    200-400+ characters) so they can't overflow past their fixed-size
    button/label and bleed into whatever is drawn next."""
    if not text or len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0]
    return cut + " …"


def reshape_only(text):
    """Connect Arabic letters into their correct joined forms, without
    reordering them right-to-left yet."""
    if not text:
        return ""
    text = str(text)
    if not RESHAPE_OK:
        return text
    try:
        return _reshaper.reshape(text)
    except Exception:
        return text


_LATIN_RUN = re.compile(r'[A-Za-zÀ-ÖØ-öø-ÿ]+')
# ANY punctuation/symbol character - not just brackets - turned out to
# come back as a missing-glyph box once it went through our manual
# reshape+bidi reordering: plain hyphens between two Arabic words,
# ellipsis "...", not just parentheses. Rather than chase each symbol
# one at a time, route every non-letter/non-digit/non-space character
# through Roboto (full ASCII/common-symbol coverage) the same way we
# already do for Latin words.
_LATIN_OR_SYMBOL = re.compile(r'[A-Za-zÀ-ÖØ-öø-ÿ]+|[^\w\s]+', re.UNICODE)


def mark_latin_runs(text):
    """Wrap runs of Latin letters, and any punctuation/symbol
    character, in [font=Roboto]...[/font] markup so they render with a
    font that actually has full glyph coverage for them, while
    everything else keeps using the Arabic font. Many Arabic system
    fonts (e.g. NotoNaskhArabic) are subsetted for Arabic script +
    digits only, so scientific names, English quotes, parentheses,
    hyphens, ellipses, etc. embedded in Arabic text show as
    missing-glyph boxes without this. Must be called on markup=True
    widgets, and only AFTER reshape/bidi so the injected tag characters
    don't get counted by the plain-character word-wrap length estimate.
    """
    if not text or not _LATIN_OR_SYMBOL.search(text):
        return escape_markup(text) if text else text

    out = []
    last = 0
    for m in _LATIN_OR_SYMBOL.finditer(text):
        out.append(escape_markup(text[last:m.start()]))
        out.append(f"[font=Roboto]{escape_markup(m.group())}[/font]")
        last = m.end()
    out.append(escape_markup(text[last:]))
    return "".join(out)


def ar(text):
    """Reshape + bidi-reorder a single line of text. Only safe for text
    that is already short enough to never wrap - if Kivy wraps a
    bidi-reordered string itself, the result comes out scrambled. For
    anything that might span multiple lines, use ar_wrap() instead.
    Does NOT wrap Latin runs in font markup - use ar_markup() for that,
    on widgets that actually support markup=True (Popup.title does not)."""
    if not text:
        return ""
    text = str(text)
    if not RESHAPE_OK:
        return text
    try:
        return get_display(reshape_only(text))
    except Exception:
        return text


def ar_markup(text):
    """Same as ar(), but also wraps embedded Latin runs in
    [font=Roboto] markup. Only use on widgets with markup=True."""
    return mark_latin_runs(ar(text))


def _font_size_to_px(font_size):
    """Turn '18sp' (or a plain number) into device pixels."""
    try:
        if isinstance(font_size, str) and font_size.endswith("sp"):
            return sp(float(font_size[:-2]))
        return sp(float(font_size))
    except Exception:
        return sp(16)


def ar_wrap(text, font_size="16sp", max_width_px=None, chars_ratio=0.62):
    """Wrap Arabic text ourselves BEFORE bidi-reordering, then reorder
    each finished line on its own. This avoids the classic Kivy+Arabic
    bug where letting Kivy word-wrap an already-bidi-reordered string
    scrambles the line order. The character-per-line estimate is
    approximate (based on average glyph width for the font size), not
    pixel-perfect, but keeps lines from scrambling."""
    if not text:
        return ""
    text = str(text)
    if not RESHAPE_OK or not has_arabic(text):
        # Pure Latin/numeric text (e.g. scientific species names that
        # show up as-is in a few tariff entries) - let Kivy's normal
        # LTR wrapping handle it instead of our RTL-oriented logic.
        return mark_latin_runs(text)

    if max_width_px is None:
        max_width_px = max(Window.width - dp(72), dp(120))

    font_px = _font_size_to_px(font_size)
    avg_char_px = max(font_px * chars_ratio, 1)
    max_chars = max(8, int(max_width_px / avg_char_px))

    # Handle any literal newlines (e.g. a quote line followed by an
    # "- author" line) as separate paragraphs FIRST. Passing a raw \n
    # control character into arabic_reshaper mid-word corrupts the
    # letter-joining/shaping state machine and can make the whole line
    # render as unsupported glyphs (empty boxes) - so we must never let
    # one slip into a "word" that gets reshaped.
    paragraphs = text.split("\n")
    all_lines = []
    for para in paragraphs:
        words = para.split(" ")
        lines = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if len(trial) <= max_chars or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)  # keep even if empty, to preserve blank paragraph lines
        all_lines.extend(lines)

    try:
        return "\n".join(
            mark_latin_runs(get_display(reshape_only(line))) if line else ""
            for line in all_lines
        )
    except Exception:
        return mark_latin_runs(text)


# ---------- Font setup ----------
APP_DIR = os.path.dirname(os.path.abspath(__file__))

CANDIDATE_FONTS = [
    os.path.join(APP_DIR, "arabic_font.ttf"),
    "/system/fonts/NotoNaskhArabic-Regular.ttf",
    "/system/fonts/NotoSansArabic-Regular.ttf",
    "/system/fonts/NotoNaskhArabicUI-Regular.ttf",
]

ARABIC_FONT_NAME = "Roboto"  # Kivy default fallback
for candidate in CANDIDATE_FONTS:
    if os.path.exists(candidate):
        try:
            LabelBase.register(name="ArabicFont", fn_regular=candidate)
            ARABIC_FONT_NAME = "ArabicFont"
            break
        except Exception:
            pass

FONT_FOUND = ARABIC_FONT_NAME == "ArabicFont"

# ---------- Color palette (modern/professional, dark theme) ----------
COL_BG = (0.07, 0.09, 0.13, 1)          # near-black navy
COL_PANEL = (0.11, 0.14, 0.19, 1)       # panel navy
COL_ACCENT = (0.0, 0.68, 0.6, 1)        # teal accent
COL_GOLD = (0.85, 0.68, 0.24, 1)        # gold accent
COL_TEXT = (0.93, 0.94, 0.96, 1)
COL_MUTED = (0.62, 0.66, 0.72, 1)
COL_CORRECT = (0.85, 0.16, 0.16, 1)     # RED = correct answer (per user preference)
COL_WRONG = (0.13, 0.62, 0.30, 1)       # GREEN = wrong answer (per user preference)

DIFFICULTY_LABELS = {
    "easy": "سهل",
    "medium": "متوسط",
    "expert": "خبير",
}
DIFFICULTY_ORDER = ["easy", "medium", "expert"]

DATA_PATH = os.path.join(APP_DIR, "hs_codes_ar.json")
QUOTES_AR_PATH = os.path.join(APP_DIR, "quotes_ar.json")
QUOTES_EN_PATH = os.path.join(APP_DIR, "quotes_en.json")
PROGRESS_PATH = os.path.join(APP_DIR, "progress.json")

TEST_LENGTH = 20


# ---------- Data helpers ----------

def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def expand_hs_data(raw):
    """Turn the compact grouped-by-heading JSON into a flat list of
    codes, each carrying its own full breadcrumb description.
    Supports both the new grouped format and the old flat format,
    so an old data file still works."""
    flat = []
    if not raw:
        return flat

    if isinstance(raw[0], dict) and "items" in raw[0]:
        # New grouped format
        for heading in raw:
            heading_desc = heading.get("heading_description", "")
            chapter = heading.get("heading", "")
            difficulty = heading.get("difficulty", "medium")
            for item in heading.get("items", []):
                sub = item.get("sub_description", "")
                full_desc = f"{heading_desc} - {sub}" if sub else heading_desc
                short_desc = sub.split(" - ")[-1] if sub else heading_desc
                flat.append({
                    "code": item["code"],
                    "chapter": chapter,
                    "heading_description": heading_desc,
                    "full_description": full_desc,
                    "short_description": short_desc,
                    "difficulty": difficulty,
                })
    else:
        # Old flat format (already has all fields)
        flat = raw

    # Clean every text field once here, so every screen downstream
    # (quiz options, hints, explanations, stats) automatically gets
    # bidi-control-free, ASCII-punctuation text without needing to
    # remember to clean it at each call site.
    text_fields = ("heading_description", "full_description", "short_description")
    for entry in flat:
        for field in text_fields:
            if field in entry:
                entry[field] = clean_ar_text(entry[field])

    return flat


def load_progress():
    default = {
        "total_answered": 0,
        "total_correct": 0,
        "daily_goal": 20,
        "today_date": str(date.today()),
        "today_answered": 0,
        "streak": 0,
        "last_completed_date": None,
        "test_history": [],
    }
    data = load_json(PROGRESS_PATH, default)
    if data.get("today_date") != str(date.today()):
        data["today_date"] = str(date.today())
        data["today_answered"] = 0
    return data


def save_progress(data):
    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def record_answer(progress, correct):
    progress["total_answered"] += 1
    progress["today_answered"] += 1
    if correct:
        progress["total_correct"] += 1
    if progress["today_answered"] >= progress["daily_goal"]:
        today = str(date.today())
        if progress["last_completed_date"] != today:
            progress["last_completed_date"] = today
            progress["streak"] += 1
    save_progress(progress)


def grade_label(pct):
    if pct >= 90:
        return "ممتاز"
    elif pct >= 75:
        return "جيد جدا"
    elif pct >= 60:
        return "جيد"
    elif pct >= 40:
        return "مقبول"
    else:
        return "ضعيف - يحتاج مراجعة"


def build_explanation(item):
    return (
        f'الرمز {item["code"]} يقع ضمن البند {item.get("chapter", "")}\n'
        f'الذي يشمل: {item["heading_description"]}\n'
        f'وتحديدا: {item["short_description"]}'
    )


# ---------- Styled widgets ----------

class PanelBox(BoxLayout):
    """A BoxLayout with a solid background color."""
    def __init__(self, bg=COL_PANEL, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*bg)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self._rect.pos = self.pos
        self._rect.size = self.size


def arabic_label(text, font_size="18sp", color=COL_TEXT, bold=False, halign="right", **kwargs):
    lbl = Label(
        text=ar_wrap(text, font_size=font_size),
        font_size=font_size,
        font_name=ARABIC_FONT_NAME,
        color=color,
        bold=bold,
        halign=halign,
        valign="middle",
        markup=True,
        **kwargs,
    )
    lbl.bind(size=lambda s, w: setattr(s, "text_size", (w[0], None)))
    return lbl


def arabic_button(text, bg=COL_ACCENT, font_size="16sp", halign="center", **kwargs):
    btn = Button(
        text=ar_wrap(text, font_size=font_size),
        font_name=ARABIC_FONT_NAME,
        font_size=font_size,
        background_normal="",
        background_color=bg,
        color=(1, 1, 1, 1),
        halign=halign,
        valign="middle",
        markup=True,
        **kwargs,
    )
    btn.bind(size=lambda s, w: setattr(s, "text_size", (w[0] - dp(10), None)))
    return btn


def show_popup(title, message, on_close=None, title_color=COL_TEXT):
    box = PanelBox(orientation="vertical", padding=dp(18), spacing=dp(12), bg=COL_PANEL)
    scroll = ScrollView(size_hint=(1, 0.75))
    msg_label = arabic_label(message, font_size="15sp", size_hint_y=None)
    msg_label.bind(texture_size=lambda s, ts: setattr(s, "height", ts[1]))
    scroll.add_widget(msg_label)
    box.add_widget(scroll)
    btn = arabic_button("موافق", bg=COL_ACCENT, size_hint=(1, 0.25))
    box.add_widget(btn)

    popup = Popup(
        title=ar(title),
        title_font=ARABIC_FONT_NAME,
        title_color=title_color,
        content=box,
        size_hint=(0.9, 0.6),
        separator_color=COL_ACCENT,
    )
    btn.bind(on_release=popup.dismiss)
    if on_close:
        popup.bind(on_dismiss=lambda x: on_close())
    popup.open()


# ---------- Screens ----------

class MenuScreen(Screen):
    def on_pre_enter(self, *args):
        self.clear_widgets()
        app = App.get_running_app()
        progress = app.progress

        root = PanelBox(orientation="vertical", padding=dp(20), spacing=dp(14), bg=COL_BG)

        if not FONT_FOUND:
            root.add_widget(arabic_label(
                "تنبيه: لم يتم العثور على خط عربي. أضف arabic_font.ttf لعرض أفضل.",
                font_size="12sp", color=COL_GOLD, size_hint=(1, 0.06)
            ))

        quote = random.choice(app.quotes) if app.quotes else {"text": "", "author": ""}
        q_text = quote.get("text", "")
        q_author = quote.get("author", "")
        is_ar_quote = quote.get("lang") == "ar"
        # Arabic guillemets «» read naturally in RTL text; ASCII "" is kept
        # only for English quotes where no RTL/mirroring is involved.
        if is_ar_quote:
            quote_text = f'«{q_text}»\n- {q_author}'
        else:
            quote_text = f'"{q_text}"\n- {q_author}'
        # Use the same arabic_label() helper as every other widget in the
        # app (rather than a separately hand-built Label) so this gets
        # identical, already-proven-working text handling.
        if is_ar_quote:
            q_label = arabic_label(quote_text, font_size="15sp", color=COL_GOLD,
                                    halign="center", size_hint=(1, 0.2))
        else:
            # English quotes must NOT use the Arabic-script font: system
            # Arabic fonts (e.g. NotoNaskhArabic) are subsetted for Arabic
            # + digits and often lack most of the Latin alphabet, so a
            # full English sentence renders as a wall of missing-glyph
            # boxes. Kivy's built-in "Roboto" has complete Latin coverage.
            q_label = Label(
                text=quote_text,
                font_size="15sp",
                font_name="Roboto",
                color=COL_GOLD,
                halign="center",
                valign="middle",
                size_hint=(1, 0.2),
            )
            q_label.bind(size=lambda s, w: setattr(s, "text_size", w))
        root.add_widget(q_label)

        root.add_widget(arabic_label("رفيقك في حفظ الرموز الجمركية", font_size="26sp",
                                      bold=True, color=COL_ACCENT, halign="center",
                                      size_hint=(1, 0.1)))

        root.add_widget(arabic_label("نسخة الفحص رقم ثلاثة", font_size="11sp",
                                      color=(0.9, 0.2, 0.2, 1), halign="center",
                                      size_hint=(1, 0.04)))

        goal_text = f"الهدف اليومي: {progress['today_answered']} من {progress['daily_goal']}    التتابع: {progress['streak']} يوم"
        root.add_widget(arabic_label(goal_text, font_size="15sp", halign="center", size_hint=(1, 0.08)))

        pb = ProgressBar(max=progress["daily_goal"],
                          value=min(progress["today_answered"], progress["daily_goal"]),
                          size_hint=(1, 0.05))
        root.add_widget(pb)

        btn_practice = arabic_button("تدريب حر", bg=COL_ACCENT, size_hint=(1, 0.13))
        btn_practice.bind(on_release=lambda x: self.go_to_difficulty("quiz"))
        root.add_widget(btn_practice)

        btn_test = arabic_button(f"اختبار من {TEST_LENGTH} سؤال مع علامة نهائية", bg=COL_GOLD, size_hint=(1, 0.13))
        btn_test.bind(on_release=lambda x: self.go_to_difficulty("test"))
        root.add_widget(btn_test)

        btn_stats = arabic_button("الإحصائيات والسجل", bg=(0.25, 0.28, 0.34, 1), size_hint=(1, 0.13))
        btn_stats.bind(on_release=lambda x: setattr(self.manager, "current", "stats"))
        root.add_widget(btn_stats)

        self.add_widget(root)

    def go_to_difficulty(self, mode):
        diff_screen = self.manager.get_screen("difficulty")
        diff_screen.target_mode = mode
        self.manager.current = "difficulty"


class DifficultyScreen(Screen):
    target_mode = "quiz"

    def on_pre_enter(self, *args):
        self.clear_widgets()
        root = PanelBox(orientation="vertical", padding=dp(24), spacing=dp(16), bg=COL_BG)
        root.add_widget(arabic_label("اختر مستوى الصعوبة", font_size="22sp", bold=True,
                                      color=COL_ACCENT, halign="center", size_hint=(1, 0.15)))

        descs = {
            "easy": "تلميح كامل يظهر وصف البند - مناسب للمبتدئين",
            "medium": "تلميح رقم الفصل فقط",
            "expert": "بدون أي تلميح - للمحترفين",
        }
        for level in DIFFICULTY_ORDER:
            box = BoxLayout(orientation="vertical", size_hint=(1, 0.22), spacing=dp(4))
            btn = arabic_button(DIFFICULTY_LABELS[level], bg=COL_ACCENT, font_size="20sp", size_hint=(1, 0.7))
            btn.bind(on_release=lambda inst, lvl=level: self.start(lvl))
            box.add_widget(btn)
            box.add_widget(arabic_label(descs[level], font_size="12sp", color=COL_MUTED,
                                         halign="center", size_hint=(1, 0.3)))
            root.add_widget(box)

        back = arabic_button("رجوع", bg=(0.25, 0.28, 0.34, 1), size_hint=(1, 0.15))
        back.bind(on_release=lambda x: setattr(self.manager, "current", "menu"))
        root.add_widget(back)

        self.add_widget(root)

    def start(self, level):
        app = App.get_running_app()
        pool = [c for c in app.hs_codes if c.get("difficulty") == level]
        if len(pool) < 4:
            show_popup("تنبيه", "لا توجد بيانات كافية لهذا المستوى.")
            return
        if self.target_mode == "quiz":
            quiz = self.manager.get_screen("quiz")
            quiz.difficulty = level
            self.manager.current = "quiz"
        else:
            test = self.manager.get_screen("test")
            test.setup_test(level)
            self.manager.current = "test"


class QuizScreen(Screen):
    difficulty = "easy"

    def on_pre_enter(self, *args):
        self.next_question()

    def get_pool(self):
        app = App.get_running_app()
        return [c for c in app.hs_codes if c.get("difficulty") == self.difficulty]

    def next_question(self):
        self.clear_widgets()
        app = App.get_running_app()
        pool = self.get_pool()

        correct_item = random.choice(pool)
        options = [correct_item]
        others = [c for c in pool if c["code"] != correct_item["code"]]
        options += random.sample(others, min(3, len(others)))
        random.shuffle(options)

        root = PanelBox(orientation="vertical", padding=dp(18), spacing=dp(10), bg=COL_BG)

        header = arabic_label(f"تدريب حر - {DIFFICULTY_LABELS[self.difficulty]}",
                               font_size="14sp", color=COL_MUTED, halign="center", size_hint=(1, 0.06))
        root.add_widget(header)

        root.add_widget(arabic_label(f"ما وصف هذا الرمز؟\n\n{correct_item['code']}",
                                      font_size="24sp", bold=True, color=COL_GOLD,
                                      halign="center", size_hint=(1, 0.22)))

        # Difficulty-based hint
        hint = ""
        if self.difficulty == "easy":
            hint = f'تلميح: {truncate_ar(correct_item["heading_description"], 90)}'
        elif self.difficulty == "medium":
            hint = f'تلميح: الفصل {correct_item.get("chapter", "")}'
        if hint:
            root.add_widget(arabic_label(hint, font_size="13sp", color=COL_MUTED,
                                          halign="center", size_hint=(1, 0.1)))
        else:
            root.add_widget(BoxLayout(size_hint=(1, 0.02)))

        grid = GridLayout(cols=1, spacing=dp(8), size_hint=(1, 0.5))
        for opt in options:
            btn = arabic_button(truncate_ar(opt["full_description"], 90), bg=(0.16, 0.19, 0.25, 1), font_size="13sp")
            btn.bind(on_release=lambda inst, correct=(opt["code"] == correct_item["code"]),
                      item=correct_item: self.answer(correct, item))
            grid.add_widget(btn)
        root.add_widget(grid)

        back = arabic_button("القائمة الرئيسية", bg=(0.25, 0.28, 0.34, 1), size_hint=(1, 0.1))
        back.bind(on_release=lambda x: setattr(self.manager, "current", "menu"))
        root.add_widget(back)

        self.add_widget(root)

    def answer(self, correct, item):
        app = App.get_running_app()
        record_answer(app.progress, correct)
        title = "إجابة صحيحة" if correct else "إجابة خاطئة"
        title_color = COL_CORRECT if correct else COL_WRONG
        explanation = build_explanation(item)
        if not correct:
            message = f'الإجابة الصحيحة: {item["full_description"]}\n\n{explanation}'
        else:
            message = f'أحسنت!\n\n{explanation}'
        show_popup(title, message, on_close=self.next_question, title_color=title_color)


class TestScreen(Screen):
    def setup_test(self, difficulty):
        app = App.get_running_app()
        self.difficulty = difficulty
        pool = [c for c in app.hs_codes if c.get("difficulty") == difficulty]
        n = min(TEST_LENGTH, len(pool))
        self.questions = random.sample(pool, n)
        self.index = 0
        self.score = 0
        self.render_question()

    def render_question(self):
        self.clear_widgets()
        app = App.get_running_app()

        if self.index >= len(self.questions):
            self.finish_test()
            return

        current = self.questions[self.index]
        pool = [c for c in app.hs_codes if c.get("difficulty") == self.difficulty and c["code"] != current["code"]]
        options = [current] + random.sample(pool, min(3, len(pool)))
        random.shuffle(options)

        root = PanelBox(orientation="vertical", padding=dp(18), spacing=dp(10), bg=COL_BG)

        progress_text = f"سؤال {self.index + 1} من {len(self.questions)}    {DIFFICULTY_LABELS[self.difficulty]}"
        root.add_widget(arabic_label(progress_text, font_size="13sp", color=COL_MUTED,
                                      halign="center", size_hint=(1, 0.07)))

        root.add_widget(arabic_label(f"{current['code']}", font_size="26sp", bold=True,
                                      color=COL_GOLD, halign="center", size_hint=(1, 0.15)))

        grid = GridLayout(cols=1, spacing=dp(8), size_hint=(1, 0.6))
        for opt in options:
            btn = arabic_button(truncate_ar(opt["full_description"], 90), bg=(0.16, 0.19, 0.25, 1), font_size="13sp")
            btn.bind(on_release=lambda inst, correct=(opt["code"] == current["code"]),
                      item=current: self.answer(correct, item))
            grid.add_widget(btn)
        root.add_widget(grid)

        self.add_widget(root)

    def answer(self, correct, item):
        app = App.get_running_app()
        if correct:
            self.score += 1
        record_answer(app.progress, correct)
        title = "إجابة صحيحة" if correct else "إجابة خاطئة"
        title_color = COL_CORRECT if correct else COL_WRONG
        explanation = build_explanation(item)
        if not correct:
            message = f'الإجابة الصحيحة: {item["full_description"]}\n\n{explanation}'
        else:
            message = f'أحسنت!\n\n{explanation}'
        self.index += 1
        show_popup(title, message, on_close=self.render_question, title_color=title_color)

    def finish_test(self):
        app = App.get_running_app()
        progress = app.progress
        total = len(self.questions)
        pct = (self.score / total * 100) if total else 0
        progress["test_history"].append({
            "date": str(date.today()),
            "score": self.score,
            "total": total,
            "difficulty": self.difficulty,
        })
        save_progress(progress)

        self.clear_widgets()
        root = PanelBox(orientation="vertical", padding=dp(24), spacing=dp(16), bg=COL_BG)
        root.add_widget(arabic_label("انتهى الاختبار", font_size="24sp", bold=True,
                                      color=COL_ACCENT, halign="center", size_hint=(1, 0.15)))
        root.add_widget(arabic_label(f"النتيجة: {self.score} من {total} - {pct:.0f}%",
                                      font_size="26sp", bold=True, color=COL_GOLD,
                                      halign="center", size_hint=(1, 0.2)))
        root.add_widget(arabic_label(grade_label(pct), font_size="20sp", color=COL_TEXT,
                                      halign="center", size_hint=(1, 0.15)))

        btn = arabic_button("القائمة الرئيسية", bg=COL_ACCENT, size_hint=(1, 0.15))
        btn.bind(on_release=lambda x: setattr(self.manager, "current", "menu"))
        root.add_widget(btn)
        self.add_widget(root)


class StatsScreen(Screen):
    def on_pre_enter(self, *args):
        self.clear_widgets()
        app = App.get_running_app()
        p = app.progress

        root = PanelBox(orientation="vertical", padding=dp(20), spacing=dp(10), bg=COL_BG)
        root.add_widget(arabic_label("الإحصائيات", font_size="24sp", bold=True,
                                      color=COL_ACCENT, halign="center", size_hint=(1, 0.1)))

        accuracy = (p["total_correct"] / p["total_answered"] * 100) if p["total_answered"] else 0
        stats_text = (
            f"مجموع الأسئلة: {p['total_answered']}\n"
            f"الإجابات الصحيحة: {p['total_correct']}\n"
            f"نسبة الدقة: {accuracy:.1f}%\n"
            f"التتابع الحالي: {p['streak']} يوم\n"
            f"اليوم: {p['today_answered']} من {p['daily_goal']}"
        )
        root.add_widget(arabic_label(stats_text, font_size="16sp", halign="right", size_hint=(1, 0.3)))

        history = p["test_history"][-8:][::-1]
        if history:
            lines = [
                f"{h['date']} - {DIFFICULTY_LABELS.get(h.get('difficulty', ''), '-')}: {h['score']} من {h['total']}"
                for h in history
            ]
            hist_text = "آخر الاختبارات:\n" + "\n".join(lines)
        else:
            hist_text = "لم يتم إجراء أي اختبار بعد."

        scroll = ScrollView(size_hint=(1, 0.4))
        hist_label = arabic_label(hist_text, font_size="14sp", size_hint_y=None)
        hist_label.bind(texture_size=lambda s, ts: setattr(s, "height", ts[1]))
        scroll.add_widget(hist_label)
        root.add_widget(scroll)

        back = arabic_button("القائمة الرئيسية", bg=(0.25, 0.28, 0.34, 1), size_hint=(1, 0.15))
        back.bind(on_release=lambda x: setattr(self.manager, "current", "menu"))
        root.add_widget(back)

        self.add_widget(root)


class HSQuizApp(App):
    def build(self):
        Window.clearcolor = COL_BG

        raw_hs = load_json(DATA_PATH, [])
        self.hs_codes = expand_hs_data(raw_hs)

        quotes_ar = load_json(QUOTES_AR_PATH, [])
        for q in quotes_ar:
            q["lang"] = "ar"
            q["text"] = clean_ar_text(q.get("text", ""))
            q["author"] = clean_ar_text(q.get("author", ""))
        quotes_en = load_json(QUOTES_EN_PATH, [])
        for q in quotes_en:
            q["lang"] = "en"
        self.quotes = quotes_ar + quotes_en

        self.progress = load_progress()

        if not self.hs_codes:
            show_popup("بيانات مفقودة", "ملف hs_codes_ar.json فارغ أو مفقود.")

        # --- TEMPORARY DIAGNOSTIC: remove after confirming the real cause ---
        diag_lines = [
            f"RESHAPE_OK = {RESHAPE_OK}",
            f"import error: {RESHAPE_IMPORT_ERROR}",
            f"FONT_FOUND = {FONT_FOUND}",
            f"ARABIC_FONT_NAME = {ARABIC_FONT_NAME}",
        ]
        if RESHAPE_OK:
            try:
                sample = ar("رفيقك في حفظ")
                diag_lines.append(f"sample ar(): {sample!r}")
            except Exception as _diag_e:
                diag_lines.append(f"ar() crashed: {_diag_e!r}")
        show_popup("تشخيص", "\n".join(diag_lines))
        # --- END TEMPORARY DIAGNOSTIC ---

        sm = ScreenManager()
        sm.add_widget(MenuScreen(name="menu"))
        sm.add_widget(DifficultyScreen(name="difficulty"))
        sm.add_widget(QuizScreen(name="quiz"))
        sm.add_widget(TestScreen(name="test"))
        sm.add_widget(StatsScreen(name="stats"))
        return sm


if __name__ == "__main__":
    import traceback
    try:
        HSQuizApp().run()
    except Exception:
        crash_path = os.path.join(APP_DIR, "crash_log.txt")
        with open(crash_path, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
