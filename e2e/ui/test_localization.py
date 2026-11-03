"""Real browser checks for all five languages, translated catalog data and narrow screens."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from api.client import RestaurantApi
from playwright.sync_api import Page, expect

from ui.helpers.auth import login

pytestmark = pytest.mark.ui

COPY = {
    "en": {
        "menu": "Our Menu",
        "dish": "Garden salad",
        "description": "Fresh vegetables with herbs.",
        "main_course": "Main Course",
        "book": "Book a Table",
        "location": "Location",
        "price": "Price",
        "search": "Search dishes...",
        "mismatch": "Passwords do not match",
        "admin": "Admin Panel",
        "reports": "Reports",
        "report_type": "Report type",
        "sales": "Sales",
        "generate": "Generate Report",
        "waiter": "Waiter Dashboard",
        "walk_in": "Walk-in reservation",
        "guests": "Guests",
    },
    "uk": {
        "menu": "Наше меню",
        "dish": "Салат із городу",
        "description": "Свіжі овочі із зеленню.",
        "main_course": "Основні страви",
        "book": "Забронювати столик",
        "location": "Ресторан",
        "price": "Ціна",
        "search": "Пошук страв…",
        "mismatch": "Паролі не збігаються",
        "admin": "Адмін-панель",
        "reports": "Звіти",
        "report_type": "Тип звіту",
        "sales": "Продажі",
        "generate": "Сформувати звіт",
        "waiter": "Панель офіціанта",
        "walk_in": "Бронювання для відвідувача",
        "guests": "Гості",
    },
    "fr": {
        "menu": "Notre carte",
        "dish": "Salade du potager",
        "description": "Légumes frais aux herbes.",
        "main_course": "Plats principaux",
        "book": "Réserver une table",
        "location": "Restaurant",
        "price": "Prix",
        "search": "Rechercher un plat…",
        "mismatch": "Les mots de passe ne correspondent pas",
        "admin": "Administration",
        "reports": "Rapports",
        "report_type": "Type de rapport",
        "sales": "Ventes",
        "generate": "Générer le rapport",
        "waiter": "Espace serveur",
        "walk_in": "Réservation sur place",
        "guests": "Convives",
    },
    "es": {
        "menu": "Nuestra carta",
        "dish": "Ensalada de la huerta",
        "description": "Verduras frescas con hierbas.",
        "main_course": "Platos principales",
        "book": "Reservar una mesa",
        "location": "Restaurante",
        "price": "Precio",
        "search": "Buscar platos…",
        "mismatch": "Las contraseñas no coinciden",
        "admin": "Administración",
        "reports": "Informes",
        "report_type": "Tipo de informe",
        "sales": "Ventas",
        "generate": "Generar informe",
        "waiter": "Panel del camarero",
        "walk_in": "Reserva presencial",
        "guests": "Comensales",
    },
    "de": {
        "menu": "Unsere Speisekarte",
        "dish": "Gartensalat",
        "description": "Frisches Gemüse mit Kräutern.",
        "main_course": "Hauptgerichte",
        "book": "Tisch reservieren",
        "location": "Restaurant",
        "price": "Preis",
        "search": "Gerichte suchen…",
        "mismatch": "Die Passwörter stimmen nicht überein",
        "admin": "Verwaltung",
        "reports": "Berichte",
        "report_type": "Berichtstyp",
        "sales": "Umsatz",
        "generate": "Bericht erstellen",
        "waiter": "Servicebereich",
        "walk_in": "Reservierung vor Ort",
        "guests": "Gäste",
    },
}


@pytest.fixture(scope="module")
def translated_dish(api_url: str, admin_token: str, test_restaurant: dict) -> Iterator[dict]:
    """Own catalog item proves that API translations survive retrieval; no demo-seed dependency."""
    with RestaurantApi(api_url, admin_token) as api:
        dish = api._request(
            "POST",
            "/dishes",
            json={
                "name": f"AQA {COPY['en']['dish']}",
                "description": COPY["en"]["description"],
                "dishType": 1,
                "price": 17.38,
                "weight": "273 g",
                "state": "Available",
                "calories": "220 kcal",
                "proteins": "8 g",
                "fats": "10 g",
                "carbohydrates": "24 g",
                "vitamins": "A, C",
                "locationIds": [test_restaurant["location"]["id"]],
                "translations": {
                    code: {"name": copy["dish"], "description": copy["description"]} for code, copy in COPY.items()
                },
            },
        )
        try:
            yield dish
        finally:
            api.raw("DELETE", f"/dishes/{dish['id']}", params={"force": "true"})


def choose_language(page: Page, language: str) -> None:
    page.locator("select.language-select").select_option(language)
    expect(page.locator("html")).to_have_attribute("lang", language)


def assert_no_page_overflow(page: Page) -> None:
    page.evaluate("document.fonts.ready")
    measurements = page.evaluate("""() => ({
        viewport: innerWidth, width: document.documentElement.scrollWidth,
        overflowing: [...document.querySelectorAll('main *')].filter(el => {
            const box = el.getBoundingClientRect();
            return box.width > 0 && (box.right > innerWidth + 1 || box.left < -1);
        }).slice(0, 6).map(el => `${el.tagName}.${el.className}`)
    })""")
    assert measurements["width"] <= measurements["viewport"] + 1, f"{page.url}: {measurements}"


@pytest.mark.parametrize("language", COPY)
def test_public_language_catalog_and_reload(
    page: Page, base_url: str, language: str, translated_dish: dict, test_restaurant: dict
) -> None:
    copy = COPY[language]
    page.goto(f"{base_url}/menu")
    choose_language(page, language)
    expect(page.get_by_role("heading", name=copy["menu"], exact=True)).to_be_visible()
    page.get_by_role("button", name=copy["main_course"], exact=True).click()
    page.get_by_placeholder(copy["search"], exact=True).fill(copy["dish"])
    card = page.locator("button.dish-card").filter(has=page.get_by_role("heading", name=copy["dish"], exact=True))
    expect(card).to_have_count(1)
    expect(card).to_contain_text(copy["description"])
    expect(card).to_contain_text("17.38" if language == "en" else "17,38")
    card.click()
    dialog = page.get_by_role("dialog", name=copy["dish"], exact=True)
    expect(dialog.get_by_text(copy["price"], exact=True)).to_be_visible()
    expect(dialog).to_contain_text(copy["description"])
    expect(dialog).to_contain_text("273")
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
    page.reload()
    expect(page.locator("html")).to_have_attribute("lang", language)
    expect(page.locator("select.language-select")).to_have_value(language)
    expect(page.get_by_role("heading", name=copy["menu"], exact=True)).to_be_visible()
    assert page.evaluate("localStorage.getItem('restaurant.locale')") == language
    page.goto(f"{base_url}/tables?locationId={test_restaurant['location']['id']}")
    expect(page.get_by_role("heading", name=copy["book"], exact=True)).to_be_visible()
    expect(page.get_by_label(copy["location"], exact=True)).to_have_value(test_restaurant["location"]["id"])
    expect(page.get_by_label(copy["guests"], exact=True)).to_be_visible()


@pytest.mark.parametrize("language", ["fr", "de"])
@pytest.mark.parametrize("width", [320, 390, 1440])
def test_long_translations_fit_public_pages(
    page: Page, base_url: str, language: str, width: int, translated_dish: dict, test_restaurant: dict
) -> None:
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(f"{base_url}/main")
    choose_language(page, language)
    for path in (
        "/main",
        "/menu",
        "/tables",
        "/signup",
        "/forgot-password",
        f"/locations/{test_restaurant['location']['id']}",
    ):
        page.goto(f"{base_url}{path}")
        expect(page.locator("select.language-select")).to_have_value(language)
        expect(page.locator("h1, h2, h3").first).to_be_visible()
        expect(page.locator(".loading-spinner")).to_have_count(0)
        if path == "/menu":
            expect(page.get_by_role("heading", name=COPY[language]["dish"], exact=True)).to_be_visible()
        assert_no_page_overflow(page)


def test_switching_language_keeps_registration_draft_and_updates_errors(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/signup")
    values = ["Олена", "Коваль", "draft@example.com", "weak", "different"]
    fields = page.locator("form.auth-form input")
    for index, value in enumerate(values):
        fields.nth(index).fill(value)
    page.get_by_role("button", name="Create Account", exact=True).click()
    for language, copy in COPY.items():
        choose_language(page, language)
        expect(page.get_by_text(copy["mismatch"], exact=True)).to_be_visible()
        for index, value in enumerate(values):
            expect(fields.nth(index)).to_have_value(value)


@pytest.mark.parametrize("language", COPY)
def test_staff_controls_translate_without_changing_values(
    page: Page, base_url: str, language: str, test_restaurant: dict
) -> None:
    copy = COPY[language]
    login(page, base_url, os.environ["ADMIN_EMAIL"], os.environ["ADMIN_PASSWORD"])
    choose_language(page, language)
    for path, title in (("/admin", "admin"), ("/reports", "reports")):
        page.goto(f"{base_url}{path}")
        expect(page.get_by_role("heading", name=copy[title], exact=True)).to_be_visible()
        if path == "/reports":
            report_type = page.get_by_label(copy["report_type"], exact=True)
            expect(report_type).to_have_value("1")
            expect(report_type.locator("option:checked")).to_have_text(copy["sales"])
            expect(page.get_by_role("button", name=copy["generate"], exact=True)).to_be_visible()
        if language in {"fr", "de"}:
            for width in (320, 390, 1440):
                page.set_viewport_size({"width": width, "height": 900})
                assert_no_page_overflow(page)
    choose_language(page, "en")
    page.get_by_role("button", name="Logout", exact=True).click()
    login(page, base_url, test_restaurant["waiter_email"], test_restaurant["waiter_password"])
    choose_language(page, language)
    page.goto(f"{base_url}/waiter-reservations")
    expect(page.get_by_role("heading", name=copy["waiter"], exact=True)).to_be_visible()
    page.get_by_role("button", name=f"+ {copy['walk_in']}", exact=True).click()
    dialog = page.get_by_role("dialog", name=copy["walk_in"], exact=True)
    expect(dialog).to_be_visible()
    expect(dialog.get_by_label(copy["guests"], exact=True)).to_have_value("2")
    expect(dialog.locator(f"select option[value='{test_restaurant['table']['id']}']")).to_have_count(1)
    if language in {"fr", "de"}:
        for width in (320, 390, 1440):
            page.set_viewport_size({"width": width, "height": 900})
            assert_no_page_overflow(page)
    page.keyboard.press("Escape")
    expect(dialog).to_have_count(0)
