import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from robot.api import logger
from Resources.Config import Config

class TransactionTracker:
    """Library to track individual keyword executions as transactions"""
    
    ROBOT_LIBRARY_SCOPE = 'GLOBAL'
    
    def __init__(self):
        self.config = None
    
    def set_config(self, config):
        """Set the config object to track transactions"""
        self.config = config
        logger.console("TransactionTracker initialized with config")
    
    def set_total_transactions(self, total_count):
        """Set the total number of transactions that will be processed (upfront)"""
        if self.config is None:
            logger.warn("Config not set in TransactionTracker. Call 'Set Config' first.")
            return
        
        self.config.Log_Transactions = int(total_count)
        logger.console(f"Total Transactions Set: {self.config.Log_Transactions}")
        logger.info(f"Total Transactions Set: {self.config.Log_Transactions}")
    
    def start_transaction(self, transaction_name):
        """Call this at the start of each keyword - just for logging, doesn't increment total"""
        if self.config is None:
            logger.warn("Config not set in TransactionTracker. Call 'Set Config' first.")
            return
        
        self.config.TransactionItem = {"name": transaction_name}
        logger.console(f"Transaction Started: {transaction_name}")
    
    def end_transaction_success(self):
        """Call this at the end of a successful keyword execution"""
        if self.config is None:
            logger.warn("Config not set in TransactionTracker")
            return
        
        # Completed: items processed with success
        self.config.Log_Done += 1
        # TechnicallyChecked: items without system exceptions (success + business exceptions)
        self.config.Log_Looping += 1
        logger.console(f"Transaction Completed Successfully (Completed: {self.config.Log_Done}, TechnicallyChecked: {self.config.Log_Looping})")
    
    def end_transaction_business_exception(self, error_message="Business exception"):
        """Call this when a business exception occurs"""
        if self.config is None:
            logger.warn("Config not set in TransactionTracker")
            return
        
        # Business exceptions are technically checked (just not completed successfully)
        self.config.Log_Looping += 1
        logger.console(f"Transaction Business Exception: {error_message} (TechnicallyChecked: {self.config.Log_Looping})")
    
    def end_transaction_system_exception(self, error_message="System exception"):
        """Call this when a system exception occurs (don't increment anything)"""
        if self.config is None:
            logger.warn("Config not set in TransactionTracker")
            return
        
        # System exceptions: don't increment Completed or TechnicallyChecked
        logger.console(f"Transaction System Exception: {error_message} (No counters incremented)")
    
    def get_transaction_counts(self):
        """Return current transaction counts for verification"""
        if self.config is None:
            return {"Transactions": 0, "Completed": 0, "TechnicallyChecked": 0}
        
        counts = {
            "Transactions": self.config.Log_Transactions,
            "Completed": self.config.Log_Done,
            "TechnicallyChecked": self.config.Log_Looping
        }
        logger.console(f"Current Counts: {counts}")
        return counts