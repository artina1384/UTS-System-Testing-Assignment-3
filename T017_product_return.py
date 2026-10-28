"""T017: Product Return Request — three Selenium browser tests."""

from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

HOME_URL = "https://opencart.abstracta.us/"
RETURN_URL = "https://opencart.abstracta.us/index.php?route=account/return/add"
SCREENSHOT_FOLDER = Path("T017_screenshots")
SCREENSHOT_FOLDER.mkdir(exist_ok=True)

# This is sample data, NOT a verified order. Replace it if you have a real test order.
TEST_ORDER_ID = "12345"


class TestFailure(Exception):
    """The website did not behave as the scenario expected."""


class ElementNotFound(Exception):
    """The page element needs to be inspected in Chrome DevTools."""


def browser_start():
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1366,900")
    return webdriver.Chrome(options=options)


def find_field(driver, placeholder):
    """Locate a text box by its visible placeholder (not an assumed ID)."""
    selector = f'input[placeholder="{placeholder}"]'
    try:
        return WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
        )
    except TimeoutException as exc:
        raise ElementNotFound(
            f"Cannot find {placeholder!r}. Inspect the input's placeholder/name/id in Chrome."
        ) from exc


def enter(driver, placeholder, value):
    field = find_field(driver, placeholder)
    field.clear()
    if value:
        field.send_keys(value)


def choose_option(driver, text):
    """Click the radio button associated with its visible label text."""
    # Typical OpenCart forms wrap a radio input inside its label.
    xpath = ("//label[contains(normalize-space(.), "
             f'"{text}")]/input[@type="radio"]')
    candidates = driver.find_elements(By.XPATH, xpath)
    if len(candidates) != 1:
        raise ElementNotFound(
            f"Could not uniquely find radio option {text!r}. Inspect its <label> and <input type='radio'>."
        )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", candidates[0])
    candidates[0].click()
    if not candidates[0].is_selected():
        raise TestFailure(f"Radio option {text!r} was not selected.")


def fill_form(driver, missing=False, invalid_email=False):
    data = {
        "First Name": "Alex",
        "Last Name": "Taylor",
        "E-Mail": "alexexample.com" if invalid_email else "alex.taylor@example.com",
        "Telephone": "0412345678",
        "Order ID": TEST_ORDER_ID,
        "Order Date": "2026-10-20",
        "Product Name": "Test Product",
        "Product Code": "TEST-001",
        "Quantity": "1",
    }
    if missing:
        for key in ("First Name", "Last Name", "E-Mail", "Telephone", "Order ID",
                    "Product Name", "Product Code"):
            data[key] = ""

    for placeholder, value in data.items():
        # The date field may be a text box with a date picker on this OpenCart demo.
        # If a placeholder differs, the program reports an ERROR for inspection.
        enter(driver, placeholder, value)

    choose_option(driver, "Faulty, please supply details")
    choose_option(driver, "No")

    # Find textarea from visible form label instead of inventing an ID.
    comments = driver.find_elements(By.CSS_SELECTOR, "textarea")
    if len(comments) != 1:
        raise ElementNotFound("Inspect the 'Faulty or other details' textarea in Chrome.")
    comments[0].clear()
    comments[0].send_keys("Product does not operate as expected.")


def open_returns(driver):
    driver.get(HOME_URL)
    try:
        link = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//footer//a[normalize-space()='Returns']"))
        )
    except TimeoutException as exc:
        raise ElementNotFound("Inspect the Customer Service > Returns footer link.") from exc
    link.click()
    WebDriverWait(driver, 10).until(
        EC.url_contains("route=account/return/add")
    )
    find_field(driver, "First Name")


def click_continue(driver):
    """Locate the return form's submit control, whether labelled Submit or Continue."""
    # OpenCart's return form may use an <input> rather than a <button>.
    # Only search inside the return form to avoid clicking unrelated controls.
    forms = driver.find_elements(By.CSS_SELECTOR, "form")
    return_forms = [form for form in forms if form.find_elements(
        By.CSS_SELECTOR, 'input[placeholder="Order ID"]'
    )]
    if len(return_forms) != 1:
        raise ElementNotFound("Cannot identify the return form. Inspect its <form> element.")

    form = return_forms[0]
    buttons = form.find_elements(
        By.CSS_SELECTOR, 'input[type="submit"], button[type="submit"]'
    )
    visible_buttons = [button for button in buttons if button.is_displayed() and button.is_enabled()]

    if len(visible_buttons) != 1:
        raise ElementNotFound(
            "Cannot uniquely identify the return form submit control. "
            "Inspect its <input>/<button> tag and type in Chrome DevTools."
        )
    button = visible_buttons[0]
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
    button.click()


def success_visible(driver):
    current_url = driver.current_url.lower()
    # Only treat a return-specific confirmation route or explicit message as success.
    return ("route=account/return/success" in current_url or
            "thank you for submitting your return request" in driver.page_source.lower())


def field_errors(driver):
    """Read all visible field errors in one DOM snapshot to avoid stale elements."""
    return driver.execute_script("""
        const fields = ['First Name', 'Last Name', 'E-Mail', 'Telephone',
                        'Order ID', 'Product Name', 'Product Code'];
        const results = {};
        for (const name of fields) {
            const field = Array.from(document.querySelectorAll('input'))
                .find(el => el.getAttribute('placeholder') === name);
            if (!field) continue;
            const messages = [];
            if (field.validity && !field.validity.valid && field.validationMessage) {
                messages.push(field.validationMessage);
            }
            const group = field.closest('.form-group');
            if (group) {
                group.querySelectorAll('.text-danger, .invalid-feedback').forEach(el => {
                    if (el.getClientRects().length && el.textContent.trim()) {
                        messages.push(el.textContent.trim());
                    }
                });
            }
            if (messages.length) results[name] = messages.join('; ');
        }
        return results;
    """)


def response_state(driver):
    """Read current URL, confirmation text and validation messages safely."""
    url = driver.current_url.lower()
    # A navigation to the success route is decisive without accessing the old form.
    if 'route=account/return/success' in url:
        return True, {}
    return success_visible(driver), field_errors(driver)


def run_scenario(number, scenario):
    driver = None
    try:
        driver = browser_start()  # New Chrome session for every scenario.
        open_returns(driver)

        if number == 1:
            fill_form(driver)
            click_continue(driver)
            WebDriverWait(driver, 10).until(lambda d: any(response_state(d)))
            accepted, errors = response_state(driver)
            if not accepted:
                raise TestFailure("Valid form was rejected: " + str(errors))
            return "PASS", "Return request accepted; confirmation displayed (order not verified)."

        if number == 2:
            fill_form(driver, missing=True)
            click_continue(driver)
            WebDriverWait(driver, 8).until(lambda d: any(response_state(d)))
            accepted, errors = response_state(driver)
            if accepted:
                raise TestFailure("Website accepted a request with mandatory fields missing.")
            expected = ("First Name", "Last Name", "E-Mail", "Telephone", "Order ID",
                        "Product Name", "Product Code")
            missing_errors = [name for name in expected if name not in errors]
            if missing_errors:
                raise TestFailure("No field-specific validation found for: " + ", ".join(missing_errors))
            return "PASS", "Incomplete form rejected with required-field errors."

        fill_form(driver, invalid_email=True)
        click_continue(driver)
        WebDriverWait(driver, 8).until(lambda d: any(response_state(d)))
        accepted, errors = response_state(driver)
        if accepted:
            raise TestFailure("Website accepted the invalid email address.")
        if "E-Mail" not in errors:
            raise TestFailure("No email-specific validation error was observed.")
        return "PASS", "Invalid email rejected with an email validation error."

    except TestFailure as exc:
        return "FAIL", str(exc)
    except (ElementNotFound, TimeoutException, WebDriverException) as exc:
        return "ERROR", str(exc).splitlines()[0]
    except Exception as exc:
        return "ERROR", f"Unexpected automation error: {exc}"
    finally:
        if driver:
            try:
                filename = SCREENSHOT_FOLDER / (
                    f"T017_{number}_{datetime.now():%Y%m%d_%H%M%S}.png"
                )
                driver.save_screenshot(str(filename))
            except WebDriverException:
                print(f"Warning: Could not save Scenario {number} screenshot.")
            driver.quit()


if __name__ == "__main__":
    results = []
    for number, name in enumerate(("Successful return", "Missing mandatory fields",
                                   "Invalid email"), start=1):
        status, explanation = run_scenario(number, name)
        if status == "ERROR" and any(message in explanation.lower() for message in (
                "stale element", "node with given id", "does not belong to the document")):
            # Retry once using a new browser session for a temporary DOM/driver error.
            status, explanation = run_scenario(number, name)
        results.append(status)
        print(f"Scenario {number}: {status} - {explanation}")
    print(f"Summary: {results.count('PASS')} PASS, "
          f"{results.count('FAIL')} FAIL, {results.count('ERROR')} ERROR")
