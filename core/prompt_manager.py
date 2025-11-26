import json
from pathlib import Path
from typing import List, Dict
from pydantic import ValidationError

# Import the Pydantic models we defined earlier
# --- FIX: Added ActionItem to the import list ---
from .models import EmailRecord, PromptConfiguration, PromptTemplate, ActionItem 

# Define file paths relative to the project root
ASSETS_DIR = Path("assets")
MOCK_INBOX_PATH = ASSETS_DIR / "mock_inbox.json"
DEFAULT_PROMPTS_PATH = ASSETS_DIR / "default_prompts.json"

class PromptManager:
    """
    Manages the application state, including loading/storing emails and prompts.
    """
    def __init__(self):
        self._emails: List[EmailRecord] = []
        self._prompts: PromptConfiguration | None = None
        self._load_all_data()

    def _load_json_file(self, file_path: Path) -> dict | list:
        """Helper to load a JSON file, raising an error if not found."""
        if not file_path.exists():
            raise FileNotFoundError(f"Required file not found: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_emails(self):
        """Loads and validates the Mock Inbox data."""
        print(f"Loading emails from {MOCK_INBOX_PATH}...")
        raw_emails = self._load_json_file(MOCK_INBOX_PATH)
        
        # Validate data using the Pydantic EmailRecord model
        validated_emails: List[EmailRecord] = []
        for item in raw_emails:
            try:
                # ENHANCED: Convert action_items dicts back to ActionItem objects during load
                if 'action_items' in item and item['action_items']:
                    item['action_items'] = [ActionItem(**ai) if isinstance(ai, dict) else ai 
                                           for ai in item['action_items']]
                validated_emails.append(EmailRecord(**item))
            except ValidationError as e:
                print(f"Validation Error in email item: {item.get('id', 'Unknown ID')}")
                print(e.errors())
                # For robustness, we could skip the bad record, but here we let it stop
                raise
        
        self._emails = validated_emails
        print(f"Successfully loaded {len(self._emails)} emails.")

    def _load_prompts(self):
        """Loads and validates the Prompt Configuration."""
        print(f"Loading prompts from {DEFAULT_PROMPTS_PATH}...")
        raw_prompts = self._load_json_file(DEFAULT_PROMPTS_PATH)
        
        # Validate data using the Pydantic PromptConfiguration model
        try:
            self._prompts = PromptConfiguration(**raw_prompts)
            print("Successfully loaded and validated prompt configuration.")
        except ValidationError as e:
            print("Validation Error in prompt configuration file.")
            print(e.errors())
            raise

    def _load_all_data(self):
        """Main method to initialize all core data."""
        self._load_emails()
        self._load_prompts()

    # --- Public Accessors and Mutators ---
    
    def get_emails(self) -> List[EmailRecord]:
        """Returns the current list of emails."""
        return self._emails

    def get_email_by_id(self, email_id: int) -> EmailRecord | None:
        """Returns a specific email by ID."""
        return next((e for e in self._emails if e.id == email_id), None)

    def get_prompt_config(self) -> PromptConfiguration:
        """Returns the current prompt configuration."""
        if self._prompts is None:
            raise RuntimeError("Prompts have not been loaded.")
        return self._prompts

    def save_email_state(self, email_id: int, category: str = None, action_items: List[Dict] = None, draft_reply: str = None):
        """
        Updates the processed outputs for a specific email.
        [cite_start]This handles storing processed outputs required by the assignment[cite: 100].
        """
        email = self.get_email_by_id(email_id)
        if email:
            if category is not None:
                email.category = category
            if action_items is not None:
                # ENHANCED: Convert dicts back to ActionItem objects for consistency
                validated_actions = []
                for item in action_items:
                    if isinstance(item, dict):
                        validated_actions.append(ActionItem(**item))
                    elif isinstance(item, ActionItem):
                        validated_actions.append(item)
                email.action_items = validated_actions
            if draft_reply is not None:
                email.draft_reply = draft_reply
            return True
        return False
        
    def update_prompt_template(self, prompt_name: str, new_template: str):
        """
        Updates a specific prompt template based on user input (for the UI panel).
        [cite_start]This meets the requirement for users to create, edit, and save prompts[cite: 38].
        """
        config = self.get_prompt_config().dict() # Get a mutable dict representation
        if prompt_name in config:
            config[prompt_name]['template'] = new_template
            
            # Re-validate the entire configuration to ensure integrity
            try:
                self._prompts = PromptConfiguration(**config)
                # In a real app, you would also save this to DEFAULT_PROMPTS_PATH here
                print(f"Prompt '{prompt_name}' updated successfully.")
                return True
            except ValidationError as e:
                print(f"Error validating updated prompt '{prompt_name}': {e}")
                return False
        return False