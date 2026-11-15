import os

# Set these values in the hosting provider's Environment settings.
# Never put real passwords, payment numbers, or secret keys in GitHub.
SITE_NAME = os.environ.get("SITE_NAME", "Class 9 Question Bank")
PAY_NUMBER = os.environ.get("PAY_NUMBER", "01XXXXXXXXX")
PAY_METHOD = os.environ.get("PAY_METHOD", "bKash / Nagad (Send Money)")
ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "01700000000")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "CHANGE_ADMIN_PASSWORD")
