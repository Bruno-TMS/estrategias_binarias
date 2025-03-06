import csv
import os
from datetime import datetime

class Journal:
    def __init__(self, account_type):
        self.account_type = account_type
        self.log_file = os.path.join(os.path.dirname(__file__), '../logs/journal.csv')
        self._create_log_file()

    def _create_log_file(self):
        if not os.path.exists(os.path.dirname(self.log_file)):
            os.makedirs(os.path.dirname(self.log_file))
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if os.stat(self.log_file).st_size == 0:
                writer.writerow(['Timestamp', 'Account_Type', 'Contract_ID', 'Profit', 'Status'])

    def log_trade(self, contract_id, profit, status):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, self.account_type, contract_id, profit, status])
        print(f"Log salvo: {timestamp}, {self.account_type}, {contract_id}, {profit}, {status}")