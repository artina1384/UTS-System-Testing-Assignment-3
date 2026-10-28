"""T018 - F17 Main Navigation Menu: Selenium tests for OpenCart."""

from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

HOME = "https://opencart.abstracta.us/"
SCREENSHOT_FOLDER = Path(__file__).resolve().parent / "T018_screenshots"
WAIT_SECONDS = 12

# The live page shows these category labels. Find links by their visible
# text inside #menu, without assuming a particular HTML nesting structure.
MENU = (By.CSS_SELECTOR, "#menu")
CATEGORY_NAMES = {"Cameras", "Tablets", "Desktops"}


class TestFailed(Exception):
    """The website did not meet the expected result."""


def start_browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1366,900")
    return webdriver.Chrome(options=options)


def wait_for_menu(driver):
    return WebDriverWait(driver, WAIT_SECONDS).until(
        EC.visibility_of_element_located(MENU)
    )


def find_category(driver, category):
    """Find a clickable, visible category link by its exact displayed name."""
    if category not in CATEGORY_NAMES:
        raise ValueError(f"Unknown category: {category}")

    def matching_link(browser):
        menu = browser.find_element(*MENU)
        for link in menu.find_elements(By.TAG_NAME, "a"):
            if (link.text.strip() == category and link.is_displayed()
                    and link.is_enabled()):
                return link
        return False

    try:
        return WebDriverWait(driver, WAIT_SECONDS).until(matching_link)
    except TimeoutException as error:
        raise RuntimeError(
            f"Cannot find a visible {category} link inside #menu. "
            "Inspect the blue menu's id and the category anchor text in Chrome DevTools."
        ) from error


def verify_category(driver, category, path_number):
    """Check both the destination path and the visible page heading."""
    def correct_page(browser):
        query = parse_qs(urlparse(browser.current_url).query)
        heading = browser.find_elements(By.CSS_SELECTOR, "h2, h1")
        return (query.get("path") == [str(path_number)]
                and query.get("route") == ["product/category"]
                and any(h.is_displayed() and h.text.strip() == category for h in heading))

    try:
        WebDriverWait(driver, WAIT_SECONDS).until(correct_page)
    except TimeoutException:
        raise TestFailed(
            f"Expected {category} category (path={path_number}); "
            f"actual URL: {driver.current_url}. Check the page heading."
        )
    if not wait_for_menu(driver).is_displayed():
        raise TestFailed("Navigation menu disappeared on the category page.")
    find_category(driver, category)  # Confirm this link remains available.


def click_category(driver, category, path_number):
    # Re-find the link on the current page and check its actual destination.
    link = find_category(driver, category)
    destination = link.get_attribute("href") or ""
    query = parse_qs(urlparse(destination).query)
    if (query.get("path") != [str(path_number)]
            or query.get("route") != ["product/category"]):
        raise TestFailed(
            f"{category} menu link points to {destination!r}, "
            f"not the expected category path={path_number}."
        )

    # Move the mouse to the link before clicking, as a real user would.
    # This also helps avoid clicking while a previous dropdown is active.
    ActionChains(driver).move_to_element(link).pause(0.2).click(link).perform()
    verify_category(driver, category, path_number)


def scenario_1(driver):
    driver.get(HOME)
    wait_for_menu(driver)
    click_category(driver, "Cameras", 33)
    return "Cameras page opened with correct heading; navigation menu accessible."


def desktop_dropdown(driver):
    """Find Desktops' own submenu, not another category's dropdown."""
    link = find_category(driver, "Desktops")
    parent = link.find_element(By.XPATH, "./parent::li")
    menus = parent.find_elements(By.CSS_SELECTOR, ".dropdown-menu")
    if not menus:
        raise RuntimeError(
            "Desktops dropdown element not found. Inspect the Desktops <li> "
            "and its submenu in Chrome DevTools."
        )
    return link, menus[0]


def scenario_2(driver):
    driver.get(HOME)
    wait_for_menu(driver)
    link, submenu = desktop_dropdown(driver)
    ActionChains(driver).move_to_element(link).perform()  # Hover without clicking.

    try:
        WebDriverWait(driver, 4).until(lambda d: desktop_dropdown(d)[1].is_displayed())
    except TimeoutException:
        raise TestFailed(
            "Desktops submenu did not open on hover. It may require clicking "
            "instead; verify the site's intended interaction."
        )

    submenu = desktop_dropdown(driver)[1]
    options = [a.text.strip() for a in submenu.find_elements(By.CSS_SELECTOR, "a")
               if a.text.strip()]
    if not any("PC" in option for option in options) or not any("Mac" in option for option in options):
        raise TestFailed(f"Dropdown appeared but PC/Mac subcategories were missing: {options}")

    # Move into the submenu: it should stay visible while the pointer is on it.
    ActionChains(driver).move_to_element(submenu).perform()
    if not desktop_dropdown(driver)[1].is_displayed():
        raise TestFailed("Desktops dropdown closed while pointer was over its submenu.")

    # Move to a visible region away from the menu and verify it closes.
    # Move to the page body, away from the blue navigation bar.
    ActionChains(driver).move_to_element(driver.find_element(By.TAG_NAME, "body")).move_by_offset(0, 200).perform()
    try:
        WebDriverWait(driver, 4).until(lambda d: not desktop_dropdown(d)[1].is_displayed())
    except TimeoutException:
        raise TestFailed("Desktops dropdown stayed open after moving pointer away.")

    ActionChains(driver).move_to_element(desktop_dropdown(driver)[0]).perform()
    try:
        WebDriverWait(driver, 4).until(lambda d: desktop_dropdown(d)[1].is_displayed())
    except TimeoutException:
        raise TestFailed("Desktops dropdown did not reopen when hovered again.")
    return "Desktops dropdown opened, stayed accessible, closed and reopened on hover."


def scenario_3(driver):
    driver.get(HOME)
    wait_for_menu(driver)
    click_category(driver, "Cameras", 33)
    click_category(driver, "Tablets", 57)
    click_category(driver, "Desktops", 20)
    return "Navigated Cameras → Tablets → Desktops; headings, URLs and menu verified."


def run_test(number, test_function):
    driver = None
    status = "ERROR"
    details = "Unknown automation error"
    try:
        driver = start_browser()  # New browser = independent session.
        details = test_function(driver)
        status = "PASS"
    except TestFailed as error:
        status = "FAIL"
        details = str(error)
    except (RuntimeError, TimeoutException, WebDriverException) as error:
        status = "ERROR"
        details = str(error).splitlines()[0] or type(error).__name__
    except Exception as error:
        status = "ERROR"
        details = f"{type(error).__name__}: {error}"
    finally:
        if driver is not None:
            try:
                SCREENSHOT_FOLDER.mkdir(exist_ok=True)
                filename = SCREENSHOT_FOLDER / f"T018_{number}_{datetime.now():%Y%m%d_%H%M%S}.png"
                driver.save_screenshot(str(filename))
            except WebDriverException as error:
                details += f" [Screenshot could not be saved: {type(error).__name__}]"
            driver.quit()
    print(f"Scenario {number}: {status} - {details}")
    return status


if __name__ == "__main__":
    results = [run_test(1, scenario_1), run_test(2, scenario_2), run_test(3, scenario_3)]
    print(f"Summary: {results.count('PASS')} PASS, {results.count('FAIL')} FAIL, {results.count('ERROR')} ERROR")
