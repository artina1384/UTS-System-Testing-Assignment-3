"""T016 / F7 - OpenCart Gift Certificate Purchase tests (Python 3 + Selenium)."""

from pathlib import Path
from datetime import datetime
import re

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "https://opencart.abstracta.us/"
GIFT_URL = BASE_URL + "index.php?route=account/voucher"
CART_URL = BASE_URL + "index.php?route=checkout/cart"
CHECKOUT_URL = BASE_URL + "index.php?route=checkout/checkout"
SCREENSHOT_DIR = Path("T016_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

# These input 'name' attributes are common to OpenCart voucher forms.
# If this site uses different names, inspect the fields in Chrome DevTools.
FIELDS = {
    "recipient_name": "to_name",
    "recipient_email": "to_email",
    "sender_name": "from_name",
    "sender_email": "from_email",
    "amount": "amount",
}


class TestFailure(Exception):
    """The website behaved differently from the test's expected result."""


def make_browser():
    options = webdriver.ChromeOptions()
    options.add_argument("--window-size=1366,900")
    # Recent Selenium versions use Selenium Manager to find ChromeDriver.
    return webdriver.Chrome(options=options)


def find_input(driver, field):
    selector = f'input[name="{FIELDS[field]}"]'
    return WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )


def fill_input(driver, field, value):
    element = find_input(driver, field)
    element.clear()
    if value:
        element.send_keys(value)


def fill_form(driver, recipient_name, recipient_email, amount):
    driver.get(GIFT_URL)
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="amount"]'))
    )

    fill_input(driver, "recipient_name", recipient_name)
    fill_input(driver, "recipient_email", recipient_email)
    fill_input(driver, "sender_name", "UTS Student Tester")
    fill_input(driver, "sender_email", "sender@example.com")
    fill_input(driver, "amount", amount)

    # Select an available gift theme (this site's visible options include General).
    theme = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="radio"][name="voucher_theme_id"]'))
    )
    theme.click()

    # The message is optional; fill it only if a matching textarea exists.
    messages = driver.find_elements(By.CSS_SELECTOR, 'textarea[name="message"]')
    if messages:
        messages[0].send_keys("Automated test gift certificate - no real purchase")

    # The form should have an agreement checkbox.
    agree = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'input[type="checkbox"][name="agree"]'))
    )
    if not agree.is_selected():
        agree.click()


def submit_form(driver):
    # OpenCart commonly uses a submit input; allow a button alternative.
    submit = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((
            By.XPATH,
            '//input[@type="submit" and @value="Continue"] | '
            '//button[@type="submit" and normalize-space()="Continue"]'
        ))
    )
    submit.click()

    # Wait until either navigation happens or a validation message appears.
    try:
        WebDriverWait(driver, 10).until(lambda d:
            "route=account/voucher" not in d.current_url
            or bool(d.find_elements(By.CSS_SELECTOR, '.text-danger, .alert-danger'))
        )
    except TimeoutException:
        pass  # The checks below will classify the unchanged result.


def validation_messages(driver):
    elements = driver.find_elements(By.CSS_SELECTOR, '.text-danger, .alert-danger')
    return [e.text.strip() for e in elements if e.is_displayed() and e.text.strip()]


def still_on_form(driver):
    return (
        "route=account/voucher" in driver.current_url
        and bool(driver.find_elements(By.CSS_SELECTOR, 'input[name="amount"]'))
    )


def field_errors(driver, field):
    # Obtain the error within the same form group as the relevant input.
    input_element = find_input(driver, field)
    groups = input_element.find_elements(
        By.XPATH, './ancestor::*[contains(concat(" ", normalize-space(@class), " "), " form-group ")][1]'
    )
    if not groups:
        return []
    errors = groups[0].find_elements(By.CSS_SELECTOR, '.text-danger, .invalid-feedback')
    return [e.text.strip() for e in errors if e.is_displayed() and e.text.strip()]


def page_has_amount(driver, expected):
    """Check for the amount as a currency value, not an unrelated '50'."""
    text = driver.find_element(By.TAG_NAME, "body").text
    pattern = rf'(?<!\d)\$\s*{expected}\.00(?!\d)'
    return bool(re.search(pattern, text))


def scenario_1(driver):
    fill_form(driver, "Alex Recipient", "recipient@example.com", "50")
    submit_form(driver)

    errors = validation_messages(driver)
    if errors:
        raise TestFailure("Valid form showed validation errors: " + "; ".join(errors))
    if still_on_form(driver):
        raise TestFailure("The completed form was not accepted; still on Gift Certificate form.")

    # Check the cart directly. Visiting the cart does not place an order.
    driver.get(CART_URL)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    cart_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    if "shopping cart is empty" in cart_text:
        raise TestFailure("Gift certificate was not added to the shopping cart.")
    if "gift certificate" not in cart_text:
        raise TestFailure("No gift certificate entry was found in the shopping cart.")
    if not page_has_amount(driver, "50"):
        raise TestFailure("The shopping cart does not show the expected $50.00 amount.")

    # Check that the customer can reach checkout; NEVER submit an order.
    driver.get(CHECKOUT_URL)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    checkout_text = driver.find_element(By.TAG_NAME, "body").text.lower()
    if "checkout" not in checkout_text or "shopping cart is empty" in checkout_text:
        raise TestFailure("Checkout was not accessible after adding the gift certificate.")
    if "route=checkout/checkout" not in driver.current_url:
        raise TestFailure("The site did not remain on the checkout route.")

    return "Valid form accepted; gift certificate and $50.00 found in cart; checkout accessible (no order placed)."


def scenario_2(driver):
    fill_form(driver, "Alex Recipient", "recipient@example.com", "0")
    submit_form(driver)

    amount_errors = field_errors(driver, "amount") if still_on_form(driver) else []
    other_errors = validation_messages(driver)
    if not still_on_form(driver):
        raise TestFailure("The website accepted $0 instead of keeping the user on the form.")
    if not amount_errors and not any("amount" in e.lower() for e in other_errors):
        raise TestFailure("$0 stayed on the form but no clear amount validation error appeared.")
    return "Website rejected the $0 amount with a visible validation error."


def scenario_3(driver):
    fill_form(driver, "", "", "50")
    submit_form(driver)

    if not still_on_form(driver):
        raise TestFailure("The website accepted a form with missing recipient details.")
    name_errors = field_errors(driver, "recipient_name")
    email_errors = field_errors(driver, "recipient_email")
    if not name_errors or not email_errors:
        raise TestFailure(
            "Form was not accepted, but both required recipient-field errors were not visible. "
            f"Name errors: {name_errors}; Email errors: {email_errors}"
        )
    return "Website rejected the form and showed errors for recipient name and email."


def run_test(test_id, test_function):
    driver = None
    status = "ERROR"
    explanation = "Test did not complete."
    try:
        driver = make_browser()  # A new Chrome session for each scenario.
        explanation = test_function(driver)
        status = "PASS"
    except TestFailure as exc:
        status = "FAIL"
        explanation = str(exc)
    except (TimeoutException, WebDriverException) as exc:
        status = "ERROR"
        explanation = f"Browser/element problem: {type(exc).__name__}: {str(exc).splitlines()[0]}"
    except Exception as exc:
        status = "ERROR"
        explanation = f"Unexpected problem: {type(exc).__name__}: {exc}"
    finally:
        if driver:
            try:
                path = SCREENSHOT_DIR / f"{test_id}_{datetime.now():%Y%m%d_%H%M%S}.png"
                driver.save_screenshot(str(path))
            except WebDriverException as exc:
                print(f"Warning: Screenshot could not be saved: {exc}")
            driver.quit()

    scenario_number = test_id.split("_")[-1]
    print(f"Scenario {scenario_number}: {status} - {explanation}")
    return status


if __name__ == "__main__":
    print("T016 — Gift Certificate Purchase Automated Testing\n")
    results = [
        run_test("T016_1", scenario_1),
        run_test("T016_2", scenario_2),
        run_test("T016_3", scenario_3),
    ]
    print(f"\nSummary: {results.count('PASS')} PASS, "
          f"{results.count('FAIL')} FAIL, {results.count('ERROR')} ERROR")
