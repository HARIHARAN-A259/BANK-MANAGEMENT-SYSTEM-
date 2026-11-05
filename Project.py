#File Handling
import os
import json
from datetime import datetime
FILE_NAME = "D:/Balance.json"

def save_data(data):
    with open(FILE_NAME, "w") as f:
        json.dump(data, f, indent = 4)

def load_data():
    if os.path.exists(FILE_NAME):
        try:
            with open(FILE_NAME, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}


#1. OOP
class BankAccount:
    def __init__(self, name, balance, data):
        self.name = name
        self.balance = balance
        self.data = data

    def deposit(self, amount):
        if amount > 0:
            self.balance += amount
            self.data[self.name]["balance"] = self.balance
            time = datetime.now().strftime("%Y / %m / %d | %H:%M")
            self.data[self.name]["history"].append(f"{time} --> Deposited: {amount} | Balance: {self.balance}")
            save_data(self.data)
            print(f"deposit: {amount}. New Balance: {self.balance}")

        else:
            print("deposit amount hould be positive")

    def withdraw(self, amount):
        if 0 < amount <= self.balance:
            self.balance -= amount
            self.data[self.name]["balance"] = self.balance
            time = datetime.now().strftime("%Y / %m / %d | %H:%M")
            self.data[self.name]["history"].append(f"{time} --> Withdraw: {amount} | Balance: {self.balance}")
            save_data(self.data)
            print(f"withdraw: {amount}. New Balance: {self.balance}")
            
        else:
            print("Invalid or Insufficient balance")

    def show_history(self):
        history = self.data[self.name]["history"]
        if not history:
            print("No trnasaction yet")
        else:
            print("Transaction history")
            for i in history:
                print("-", i)

    def check_balance(self):
        print("Balance: ", self.balance)


#User Interaction
data = load_data()
name = input("Enter your Name: ")
if name in data:
    print("Welcome back", name)
    balance = data[name]["balance"]

else:
    print("New Account Created")
    blance = 0
    data[name] = {
        "balance":0,
        "history":[]
    }
    save_data(data)

account = BankAccount(name, balance, data)
print(f"\nWelcome {name} to the System")

while True:
    print("\nYour Choice Below")
    print("1. Deposit")
    print("2. Withdraw")
    print("3. Check Balance")
    print("4. Show History")
    print("5. Exit")

    try:
        choice = int(input("Enter your choice: "))
    except ValueError:
        print("Please enter a Valid Number")
        continue

    if choice == 1:
        print("You have chosen to Deposite amount")
        try:
            amount = int(input("Enter the amoun to deposit: "))
        except ValueError:
            print("Enter a Valid Number")
            continue
        account.deposit(amount)
        print("Transaction Successful")

    elif choice == 2:
        print("You have chosen to Withdraw amount")
        try:
            amount = int(input("Enter the Amount to withdraw: "))
        except ValueError:
            print("Enter a Valid Number")
            continue
        account.withdraw(amount)

    elif choice == 3:
        print("Checking Balance.......")
        print(account.check_balance())

    elif choice == 4:
        account.show_history()

    elif choice == 5:
        print("Thank Your for Visitng 😊")
        break

    else:
        print("Invalid choice")