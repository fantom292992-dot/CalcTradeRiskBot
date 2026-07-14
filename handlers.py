"""
handlers.py — всі хендлери бота.
Session та UserRepo прокидаються автоматично через DbSessionMiddleware.
"""

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from decimal import Decimal, InvalidOperation

from database import UserRepo, UserSettings

router = Router()

# ──────────────────────────────────────────────
# FSM States
# ──────────────────────────────────────────────

class CalcStates(StatesGroup):
    waiting_for_prices = State()

class SettingsStates(StatesGroup):
    waiting_for_value = State()

# ──────────────────────────────────────────────
# Field metadata
# ──────────────────────────────────────────────

FIELD_LABELS: dict[str, str] = {
    "exchange_risk_1": "Exchange Risk 1 ($)",
    "exchange_risk_2": "Exchange Risk 2 ($)",
    "prop_balance":    "Prop Balance ($)",
    "prop_risk_1":     "Prop Risk 1 (%)",
    "prop_risk_2":     "Prop Risk 2 (%)",
}

# ──────────────────────────────────────────────
# Keyboards
# ──────────────────────────────────────────────

def main_menu_kb():
    builder = ReplyKeyboardBuilder()
    builder.button(text="⚙️ Параметри")
    builder.button(text="🧮 Порахувати ризик")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

def settings_inline_kb(s: UserSettings):
    builder = InlineKeyboardBuilder()
    rows = [
        ("exchange_risk_1", f"Exchange Risk 1: ${s.exchange_risk_1}"),
        ("exchange_risk_2", f"Exchange Risk 2: ${s.exchange_risk_2}"),
        ("prop_balance",    f"Prop Balance: ${s.prop_balance}"),
        ("prop_risk_1",     f"Prop Risk 1: {s.prop_risk_1}%"),
        ("prop_risk_2",     f"Prop Risk 2: {s.prop_risk_2}%"),
    ]
    for field, label in rows:
        builder.button(text=f"✏️ {label}", callback_data=f"edit:{field}")
    builder.button(text="❌ Закрити", callback_data="close_settings")
    builder.adjust(1)
    return builder.as_markup()

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def escape_md(text: str) -> str:
    """Екранує всі зарезервовані символи MarkdownV2 (офіційний список Telegram)."""
    # Telegram вимагає екранування цих символів: _ * [ ] ( ) ~ ` > # + - = | { } . !
    reserved = r"\_*[]()~`>#+-=|{}.!"
    result = []
    for ch in str(text):
        if ch in reserved:
            result.append("\\" + ch)
        else:
            result.append(ch)
    return "".join(result)

def calculate_position_size(entry: Decimal, stop: Decimal, risk_usd: Decimal) -> Decimal:
    """Notional Value = (Risk / |Entry - Stop|) x Entry"""
    diff = abs(entry - stop)
    if diff == 0:
        raise ValueError("Entry price equals Stop price")
    return round((risk_usd / diff) * entry, 2)

def format_report(
    entry: Decimal, stop: Decimal,
    ex1: Decimal, ex2: Decimal,
    prop1: Decimal, prop2: Decimal,
    s: UserSettings,
) -> str:
    ex_r1 = Decimal(str(s.exchange_risk_1))
    ex_r2 = Decimal(str(s.exchange_risk_2))
    p_bal = Decimal(str(s.prop_balance))
    p_r1  = Decimal(str(s.prop_risk_1))
    p_r2  = Decimal(str(s.prop_risk_2))

    prop_risk1_usd = round(p_bal * p_r1 / 100, 2)
    prop_risk2_usd = round(p_bal * p_r2 / 100, 2)

    lines = [
        "📊 *POSITION SIZE REPORT*",
        "",
        "Entry: `" + str(entry) + "` \u2502 Stop: `" + str(stop) + "`",
        "",
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
        "🏦 *EXCHANGE*",
        "",
        "Risk 1 \\(" + escape_md("$" + str(ex_r1)) + "\\):",
        "`" + str(ex1) + "`",
        "",
        "Risk 2 \\(" + escape_md("$" + str(ex_r2)) + "\\):",
        "`" + str(ex2) + "`",
        "",
        "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501",
        "🏢 *PROP FIRM*",
        "",
        "Balance: " + escape_md("$" + str(p_bal)),
        "",
        "Risk 1 \\(" + escape_md(str(p_r1) + "% = $" + str(prop_risk1_usd)) + "\\):",
        "`" + str(prop1) + "`",
        "",
        "Risk 2 \\(" + escape_md(str(p_r2) + "% = $" + str(prop_risk2_usd)) + "\\):",
        "`" + str(prop2) + "`",
    ]
    return "\n".join(lines)

# ──────────────────────────────────────────────
# Handlers
# ──────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, repo: UserRepo):
    await state.clear()
    await repo.get_or_create(message.from_user.id)
    await message.answer(
        "👋 Вітаю\\! Я бот для розрахунку розміру позиції\\.\n\n"
        "Натисни *🧮 Порахувати ризик* та введи ціни\\.",
        parse_mode="MarkdownV2",
        reply_markup=main_menu_kb(),
    )

@router.message(F.text == "⚙️ Параметри")
async def show_settings(message: Message, state: FSMContext, repo: UserRepo):
    await state.clear()
    settings = await repo.get_or_create(message.from_user.id)
    await message.answer(
        "⚙️ *Налаштування*\nОберіть параметр для редагування:",
        parse_mode="MarkdownV2",
        reply_markup=settings_inline_kb(settings),
    )

@router.callback_query(F.data.startswith("edit:"))
async def cb_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[1]
    label = FIELD_LABELS.get(field, field)
    await state.set_state(SettingsStates.waiting_for_value)
    await state.update_data(editing_field=field)
    await callback.message.answer(
        "✏️ Введіть нове значення для *" + escape_md(label) + "*:",
        parse_mode="MarkdownV2",
    )
    await callback.answer()

@router.callback_query(F.data == "close_settings")
async def cb_close_settings(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Закрито")

@router.message(SettingsStates.waiting_for_value)
async def process_setting_value(message: Message, state: FSMContext, repo: UserRepo):
    data = await state.get_data()
    field = data.get("editing_field", "")

    try:
        value = Decimal(message.text.strip().replace(",", "."))
        if value <= 0:
            raise ValueError("Value must be positive")
    except (InvalidOperation, ValueError):
        await message.answer(
            "❌ Введіть коректне позитивне число\\.",
            parse_mode="MarkdownV2",
        )
        return

    updated = await repo.update_field(message.from_user.id, field, value)
    await state.clear()

    label = FIELD_LABELS.get(field, field)
    await message.answer(
        "✅ *" + escape_md(label) + "* оновлено до `" + str(value) + "`",
        parse_mode="MarkdownV2",
        reply_markup=settings_inline_kb(updated),
    )

@router.message(F.text == "🧮 Порахувати ризик")
async def start_calculation(message: Message, state: FSMContext):
    await state.set_state(CalcStates.waiting_for_prices)
    await message.answer(
        "📥 Введіть *Entry* та *Stop* ціни через пробіл\\.\n"
        "Приклад: `2500 2400`",
        parse_mode="MarkdownV2",
    )

@router.message(CalcStates.waiting_for_prices)
async def process_prices(message: Message, state: FSMContext, repo: UserRepo):
    parts = message.text.strip().replace(",", ".").split()

    if len(parts) != 2:
        await message.answer(
            "❌ Введіть рівно *два числа* через пробіл\\.\nПриклад: `2500 2400`",
            parse_mode="MarkdownV2",
        )
        return

    try:
        entry = Decimal(parts[0])
        stop  = Decimal(parts[1])
        if entry <= 0 or stop <= 0:
            raise ValueError("Prices must be positive")
        if entry == stop:
            raise ValueError("Entry equals Stop")
    except (InvalidOperation, ValueError) as exc:
        await message.answer(
            "❌ Помилка: " + escape_md(str(exc)) + "\\.\nВведіть два коректні числа\\.",
            parse_mode="MarkdownV2",
        )
        return

    settings = await repo.get_or_create(message.from_user.id)

    try:
        p_bal = Decimal(str(settings.prop_balance))
        p_r1  = Decimal(str(settings.prop_risk_1))
        p_r2  = Decimal(str(settings.prop_risk_2))

        ex1   = calculate_position_size(entry, stop, Decimal(str(settings.exchange_risk_1)))
        ex2   = calculate_position_size(entry, stop, Decimal(str(settings.exchange_risk_2)))
        prop1 = calculate_position_size(entry, stop, round(p_bal * p_r1 / 100, 2)) / 5
        prop2 = calculate_position_size(entry, stop, round(p_bal * p_r2 / 100, 2)) / 5

    except Exception as exc:
        await message.answer(
            "❌ Помилка розрахунку: " + escape_md(str(exc)),
            parse_mode="MarkdownV2",
        )
        return

    await message.answer(
        format_report(entry, stop, ex1, ex2, prop1, prop2, settings),
        parse_mode="MarkdownV2",
    )
    await state.clear()