# =========================================================
#                ADVANCED BANK MANAGEMENT SYSTEM
# =========================================================
# FEATURES:
#
# 1. Multi User System
# 2. Deposit Money
# 3. Withdraw Money
# 4. Transfer Money
# 5. Transaction History
# 6. Password Hashing (SHA-256)
# 7. Account Lock after 3 failed attempts
# 8. Reset Password
# 9. Hidden Password using getpass
# 10. JSON File Storage
# 11. Unique Account Number Generation
# 12. Interest System
# 13. Mini Statement
# 14. Search Transaction by ID
# 15. Transaction Type Counter
# 16. Account Details Viewer
# 17. Delete Account
# 18. Change Username
# 19. Profile Management
# 20. Failed Transaction Logs
# 21. Transaction PIN
# 22. Daily Withdrawal Limit
# 23. Strong Password Validation
# 24. PIN Attempt Security
# 25. Logout System
# =========================================================


# =========================================================
#                    IMPORT MODULES
# =========================================================

import os
import json
import hashlib
import getpass
import random
import uuid

from decimal import Decimal
from datetime import datetime


# =========================================================
#                     FILE PATH
# =========================================================

FILE_NAME = "D:\\Balance.json"


# =========================================================
#                FILE HANDLING FUNCTIONS
# =========================================================

def save_data(data):

    try:

        with open(FILE_NAME, "w") as f:

            json.dump(data, f, indent=4)

    except Exception as e:

        print("❌ Error Saving Data:", e)


def load_data():

    if os.path.exists(FILE_NAME):

        try:

            with open(FILE_NAME, "r") as f:

                return json.load(f)

        except json.JSONDecodeError:

            return {}

    return {}


# =========================================================
#                PASSWORD HASHING FUNCTION
# =========================================================

def hash_password(password):

    return hashlib.sha256(password.encode()).hexdigest()


# =========================================================
#            STRONG PASSWORD VALIDATION
# =========================================================

def validate_password(password):

    has_upper = False
    has_lower = False
    has_digit = False
    has_special = False

    special_characters = "!@#$%^&*()_+-=[]{}|;:,.<>?/"

    if len(password) < 8:
        return False

    for char in password:

        if char.isupper():
            has_upper = True

        elif char.islower():
            has_lower = True

        elif char.isdigit():
            has_digit = True

        elif char in special_characters:
            has_special = True

    return (
        has_upper and
        has_lower and
        has_digit and
        has_special
    )


# =========================================================
#            ACCOUNT NUMBER GENERATION
# =========================================================

def generate_account_number(data):

    while True:

        account_number = random.randint(
            10000000,
            99999999
        )

        exists = False

        for user in data:

            if data[user].get(
                "account_number"
            ) == account_number:

                exists = True
                break

        if not exists:
            return account_number


# =========================================================
#           TRANSACTION ID GENERATION
# =========================================================

def generate_transaction_id():

    return f"TXN-{str(uuid.uuid4())[:8].upper()}"


# =========================================================
#                    LOGIN FUNCTION
# =========================================================

def login(data, name):

    if data[name].get("locked", False):

        print("❌ Account is locked")
        return None

    for attempt in range(3):

        password = getpass.getpass(
            "Enter Password: "
        )

        if hash_password(password) == data[name]["password"]:

            print("✅ Login Successful")

            print(
                f"🕒 Last Login: {data[name]['last_login']}"
            )

            current_time = datetime.now().strftime(
                "%Y/%m/%d %H:%M:%S"
            )

            data[name]["last_login"] = current_time

            save_data(data)

            return Decimal(str(data[name]["balance"]))

        else:

            print("❌ Incorrect Password")

    print("🔒 Account Locked")

    data[name]["locked"] = True

    save_data(data)

    return None


# =========================================================
#                    BANK ACCOUNT CLASS
# =========================================================

class BankAccount:


    # =====================================================
    #                    CONSTRUCTOR
    # =====================================================

    def __init__(self, name, balance, data):

        self.name = name
        self.balance = Decimal(str(balance))
        self.data = data


    # =====================================================
    #             SAVE FAILED TRANSACTION
    # =====================================================

    def save_failed_transaction(self, reason):

        time = datetime.now().strftime(
            "%Y/%m/%d %H:%M:%S"
        )

        failed_log = f"[FAILED] {time} -> {reason}"

        self.data[self.name][
            "failed_transactions"
        ].append(failed_log)

        save_data(self.data)


    # =====================================================
    #               VERIFY TRANSACTION PIN
    # =====================================================

    def verify_pin(self):

        if self.data[self.name]["pin_locked"]:

            print("❌ PIN Locked")
            return False

        for attempt in range(3):

            pin = getpass.getpass(
                "Enter Transaction PIN: "
            )

            if hash_password(pin) == self.data[self.name]["transaction_pin"]:

                self.data[self.name]["pin_attempts"] = 0

                save_data(self.data)

                return True

            else:

                print("❌ Incorrect PIN")

                self.data[self.name]["pin_attempts"] += 1

                save_data(self.data)

        self.data[self.name]["pin_locked"] = True

        save_data(self.data)

        self.save_failed_transaction(
            "PIN Locked Due To Multiple Failed Attempts"
        )

        print("🔒 PIN Locked")

        return False


    # =====================================================
    #                    DEPOSIT
    # =====================================================

    def deposit(self, amount):

        amount = Decimal(str(amount))

        if amount <= 0:

            print("❌ Invalid Amount")
            return

        self.balance += amount

        self.data[self.name]["balance"] = float(
            self.balance
        )

        time = datetime.now().strftime(
            "%Y/%m/%d %H:%M:%S"
        )

        transaction_id = generate_transaction_id()

        self.data[self.name]["history"].append(

            f"[{transaction_id}] "
            f"{time} -> Deposited ₹{amount:.2f} | "
            f"Balance ₹{self.balance:.2f}"
        )

        save_data(self.data)

        print(f"✅ Deposited ₹{amount:.2f}")

        print(f"💰 Balance ₹{self.balance:.2f}")


    # =====================================================
    #                    WITHDRAW
    # =====================================================

    def withdraw(self, amount):

        if not self.verify_pin():
            return

        amount = Decimal(str(amount))

        if amount <= 0:

            print("❌ Invalid Amount")

            self.save_failed_transaction(
                "Invalid Withdrawal Amount"
            )

            return

        today = datetime.now().strftime(
            "%Y/%m/%d"
        )

        if self.data[self.name][
            "last_withdraw_date"
        ] != today:

            self.data[self.name][
                "today_withdraw_amount"
            ] = 0

            self.data[self.name][
                "last_withdraw_date"
            ] = today

        total_today = Decimal(
            str(
                self.data[self.name][
                    "today_withdraw_amount"
                ]
            )
        ) + amount

        if total_today > Decimal(
            str(
                self.data[self.name][
                    "daily_withdraw_limit"
                ]
            )
        ):

            print("❌ Daily Withdrawal Limit Exceeded")

            return

        if amount > self.balance:

            print("❌ Insufficient Balance")

            self.save_failed_transaction(
                "Insufficient Balance During Withdrawal"
            )

            return

        self.balance -= amount

        self.data[self.name][
            "today_withdraw_amount"
        ] = float(total_today)

        self.data[self.name]["balance"] = float(
            self.balance
        )

        time = datetime.now().strftime(
            "%Y/%m/%d %H:%M:%S"
        )

        transaction_id = generate_transaction_id()

        self.data[self.name]["history"].append(

            f"[{transaction_id}] "
            f"{time} -> Withdrawn ₹{amount:.2f} | "
            f"Balance ₹{self.balance:.2f}"
        )

        save_data(self.data)

        print(f"✅ Withdrawn ₹{amount:.2f}")

        print(f"💰 Balance ₹{self.balance:.2f}")


    # =====================================================
    #                    TRANSFER
    # =====================================================

    def transfer(self, receiver, amount):

        if not self.verify_pin():
            return

        if receiver not in self.data:

            print("❌ Receiver Does Not Exist")
            return

        if receiver == self.name:

            print("❌ Cannot Transfer To Yourself")
            return

        amount = Decimal(str(amount))

        if amount <= 0:

            print("❌ Invalid Amount")
            return

        if amount > self.balance:

            print("❌ Insufficient Balance")
            return

        self.balance -= amount

        self.data[self.name]["balance"] = float(
            self.balance
        )

        receiver_balance = Decimal(
            str(self.data[receiver]["balance"])
        )

        receiver_balance += amount

        self.data[receiver]["balance"] = float(
            receiver_balance
        )

        time = datetime.now().strftime(
            "%Y/%m/%d %H:%M:%S"
        )

        transaction_id = generate_transaction_id()

        self.data[self.name]["history"].append(

            f"[{transaction_id}] "
            f"{time} -> Sent ₹{amount:.2f} "
            f"to {receiver} | "
            f"Balance ₹{self.balance:.2f}"
        )

        self.data[receiver]["history"].append(

            f"[{transaction_id}] "
            f"{time} -> Received ₹{amount:.2f} "
            f"from {self.name}"
        )

        save_data(self.data)

        print(
            f"✅ ₹{amount:.2f} transferred to {receiver}"
        )


    # =====================================================
    #                  ADD INTEREST
    # =====================================================

    def add_interest(self, rate):

        rate = Decimal(str(rate))

        if rate <= 0:

            print("❌ Invalid Interest Rate")
            return

        interest = (
            self.balance * rate
        ) / Decimal("100")

        self.balance += interest

        self.data[self.name]["balance"] = float(
            self.balance
        )

        time = datetime.now().strftime(
            "%Y/%m/%d %H:%M:%S"
        )

        transaction_id = generate_transaction_id()

        self.data[self.name]["history"].append(

            f"[{transaction_id}] "
            f"{time} -> Interest Added ₹{interest:.2f}"
        )

        save_data(self.data)

        print(f"✅ Interest Added ₹{interest:.2f}")

        print(f"💰 Balance ₹{self.balance:.2f}")


    # =====================================================
    #                SHOW HISTORY
    # =====================================================

    def show_history(self):

        history = self.data[self.name]["history"]

        if not history:

            print("❌ No Transactions")
            return

        print("\n========== HISTORY ==========")

        for item in history:

            print(item)


    # =====================================================
    #                MINI STATEMENT
    # =====================================================

    def mini_statement(self):

        history = self.data[self.name]["history"]

        if not history:

            print("❌ No Transactions")
            return

        print("\n====== MINI STATEMENT ======")

        for item in history[-5:]:

            print(item)


    # =====================================================
    #         SEARCH TRANSACTION BY ID
    # =====================================================

    def search_transaction(self, transaction_id):

        history = self.data[self.name]["history"]

        found = False

        for item in history:

            if transaction_id in item:

                print(item)

                found = True
                break

        if not found:

            print("❌ Transaction Not Found")


    # =====================================================
    #         TRANSACTION TYPE COUNTER
    # =====================================================

    def transaction_counter(self):

        history = self.data[self.name]["history"]

        deposit_count = 0
        withdraw_count = 0
        transfer_count = 0

        for item in history:

            if "Deposited" in item:
                deposit_count += 1

            elif "Withdrawn" in item:
                withdraw_count += 1

            elif "Sent" in item:
                transfer_count += 1

        print("\n====== TRANSACTION REPORT ======")

        print(f"💰 Deposits    : {deposit_count}")
        print(f"💸 Withdrawals : {withdraw_count}")
        print(f"📤 Transfers   : {transfer_count}")


    # =====================================================
    #            ACCOUNT DETAILS VIEWER
    # =====================================================

    def account_details(self):

        print("\n========== ACCOUNT DETAILS ==========")

        print(f"👤 Username : {self.name}")

        print(
            f"🏦 Account Number : "
            f"{self.data[self.name]['account_number']}"
        )

        print(f"💰 Balance : ₹{self.balance:.2f}")

        print(
            f"🕒 Last Login : "
            f"{self.data[self.name]['last_login']}"
        )


    # =====================================================
    #                RESET PASSWORD
    # =====================================================

    def reset_password(self):

        old_password = getpass.getpass(
            "Enter Old Password: "
        )

        if hash_password(old_password) != self.data[self.name]["password"]:

            print("❌ Incorrect Old Password")
            return

        while True:

            new_password = getpass.getpass(
                "Enter New Password: "
            )

            confirm_password = getpass.getpass(
                "Confirm New Password: "
            )

            if new_password != confirm_password:

                print("❌ Passwords Do Not Match")
                continue

            if not validate_password(new_password):

                print(
                    "❌ Weak Password"
                )

                continue

            self.data[self.name]["password"] = hash_password(
                new_password
            )

            save_data(self.data)

            print("✅ Password Reset Successful")

            break


    # =====================================================
    #                CHANGE USERNAME
    # =====================================================

    def change_username(self, new_name):

        if new_name in self.data:

            print("❌ Username Already Exists")
            return

        self.data[new_name] = self.data.pop(
            self.name
        )

        self.name = new_name

        save_data(self.data)

        print("✅ Username Changed Successfully")


    # =====================================================
    #                UPDATE PROFILE
    # =====================================================

    def update_profile(self):

        email = input("Enter Email: ")

        phone = input("Enter Phone: ")

        address = input("Enter Address: ")

        self.data[self.name]["email"] = email

        self.data[self.name]["phone"] = phone

        self.data[self.name]["address"] = address

        save_data(self.data)

        print("✅ Profile Updated")


    # =====================================================
    #                VIEW PROFILE
    # =====================================================

    def view_profile(self):

        print("\n========== PROFILE ==========")

        print(
            f"📧 Email : "
            f"{self.data[self.name].get('email', 'Not Set')}"
        )

        print(
            f"📱 Phone : "
            f"{self.data[self.name].get('phone', 'Not Set')}"
        )

        print(
            f"🏠 Address : "
            f"{self.data[self.name].get('address', 'Not Set')}"
        )


    # =====================================================
    #                DELETE ACCOUNT
    # =====================================================

    def delete_account(self):

        password = getpass.getpass(
            "Enter Password: "
        )

        if hash_password(password) != self.data[self.name]["password"]:

            print("❌ Incorrect Password")
            return False

        if not self.verify_pin():
            return False

        confirm = input(
            "Type DELETE to confirm: "
        )

        if confirm != "DELETE":

            print("❌ Account Deletion Cancelled")
            return False

        del self.data[self.name]

        save_data(self.data)

        print("✅ Account Deleted Successfully")

        return True


    # =====================================================
    #                CHECK BALANCE
    # =====================================================

    def check_balance(self):

        return self.balance


# =========================================================
#                    MAIN PROGRAM
# =========================================================

while True:

    data = load_data()

    print("\n========== BANK SYSTEM ==========")

    name = input("Enter Username: ").lower()

    if not name.isalpha():

        print("❌ Username Should Contain Letters Only")
        continue


    # =====================================================
    #                    LOGIN
    # =====================================================

    if name in data:

        print(f"Welcome Back {name}")

        balance = login(data, name)

        if balance is None:
            continue


    # =====================================================
    #                 REGISTRATION
    # =====================================================

    else:

        print("🆕 Create New Account")

        while True:

            password = getpass.getpass(
                "Set Password: "
            )

            if validate_password(password):
                break

            print(
                "❌ Password Must Contain:"
            )

            print("• 8 Characters")
            print("• Uppercase")
            print("• Lowercase")
            print("• Digit")
            print("• Special Character")

        while True:

            pin = getpass.getpass(
                "Set 4-Digit PIN: "
            )

            if pin.isdigit() and len(pin) == 4:
                break

            print("❌ PIN Must Be 4 Digits")

        account_number = generate_account_number(
            data
        )

        data[name] = {

            "account_number": account_number,

            "password": hash_password(password),

            "transaction_pin": hash_password(pin),

            "balance": 0,

            "history": [],

            "locked": False,

            "withdraw_limit": 50000,

            "transfer_limit": 100000,

            "daily_withdraw_limit": 20000,

            "today_withdraw_amount": 0,

            "last_withdraw_date": "",

            "last_login": "First Login",

            "failed_transactions": [],

            "email": "",

            "phone": "",

            "address": "",

            "pin_attempts": 0,

            "pin_locked": False
        }

        save_data(data)

        print("✅ Account Created")

        print(
            f"🏦 Account Number: {account_number}"
        )

        balance = 0


    # =====================================================
    #                OBJECT CREATION
    # =====================================================

    account = BankAccount(
        name,
        balance,
        data
    )

    print(f"\n🏦 Welcome {name}")


    # =====================================================
    #                    MENU
    # =====================================================

    while True:

        print("\n========== MENU ==========")

        print("1. Deposit Money")
        print("2. Withdraw Money")
        print("3. Check Balance")
        print("4. Transaction History")
        print("5. Mini Statement")
        print("6. Transfer Money")
        print("7. Add Interest")
        print("8. Search Transaction")
        print("9. Transaction Counter")
        print("10. Account Details")
        print("11. Reset Password")
        print("12. Change Username")
        print("13. Update Profile")
        print("14. View Profile")
        print("15. Delete Account")
        print("16. Logout")

        try:

            choice = int(
                input("Enter Choice: ")
            )

        except ValueError:

            print("❌ Invalid Choice")
            continue


        # =================================================
        #                    DEPOSIT
        # =================================================

        if choice == 1:

            try:

                amount = Decimal(
                    input("Enter Amount: ")
                )

                account.deposit(amount)

            except:

                print("❌ Invalid Amount")


        # =================================================
        #                    WITHDRAW
        # =================================================

        elif choice == 2:

            try:

                amount = Decimal(
                    input("Enter Amount: ")
                )

                account.withdraw(amount)

            except:

                print("❌ Invalid Amount")


        # =================================================
        #                CHECK BALANCE
        # =================================================

        elif choice == 3:

            print(
                f"💰 Balance ₹{account.check_balance():.2f}"
            )


        # =================================================
        #             TRANSACTION HISTORY
        # =================================================

        elif choice == 4:

            account.show_history()


        # =================================================
        #                MINI STATEMENT
        # =================================================

        elif choice == 5:

            account.mini_statement()


        # =================================================
        #                TRANSFER MONEY
        # =================================================

        elif choice == 6:

            receiver = input(
                "Enter Receiver Name: "
            ).lower()

            try:

                amount = Decimal(
                    input("Enter Amount: ")
                )

                account.transfer(
                    receiver,
                    amount
                )

            except:

                print("❌ Invalid Amount")


        # =================================================
        #                 ADD INTEREST
        # =================================================

        elif choice == 7:

            try:

                rate = Decimal(
                    input("Enter Interest Rate: ")
                )

                account.add_interest(rate)

            except:

                print("❌ Invalid Rate")


        # =================================================
        #          SEARCH TRANSACTION
        # =================================================

        elif choice == 8:

            transaction_id = input(
                "Enter Transaction ID: "
            )

            account.search_transaction(
                transaction_id
            )


        # =================================================
        #          TRANSACTION COUNTER
        # =================================================

        elif choice == 9:

            account.transaction_counter()


        # =================================================
        #           ACCOUNT DETAILS
        # =================================================

        elif choice == 10:

            account.account_details()


        # =================================================
        #            RESET PASSWORD
        # =================================================

        elif choice == 11:

            account.reset_password()


        # =================================================
        #            CHANGE USERNAME
        # =================================================

        elif choice == 12:

            new_name = input(
                "Enter New Username: "
            ).lower()

            account.change_username(
                new_name
            )


        # =================================================
        #              UPDATE PROFILE
        # =================================================

        elif choice == 13:

            account.update_profile()


        # =================================================
        #               VIEW PROFILE
        # =================================================

        elif choice == 14:

            account.view_profile()


        # =================================================
        #              DELETE ACCOUNT
        # =================================================

        elif choice == 15:

            deleted = account.delete_account()

            if deleted:
                break


        # =================================================
        #                  LOGOUT
        # =================================================

        elif choice == 16:

            print("👋 Logged Out Successfully")
            break


        # =================================================
        #               INVALID CHOICE
        # =================================================

        else:

            print("❌ Invalid Choice")