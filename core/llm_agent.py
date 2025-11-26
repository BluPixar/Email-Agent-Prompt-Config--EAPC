import os
import json
from typing import List, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_groq import ChatGroq
from .models import EmailRecord, PromptConfiguration, ActionItem, ActionItemList
from .prompt_manager import PromptManager

# --- Configuration ---
# Try to initialize LLM, fall back to None if API key is missing
try:
    LLM = ChatGroq(model="mixtral-8x7b-32768", temperature=0)
    print(" LLM initialized successfully with Groq API")
except Exception as e:
    LLM = None
    print(f" LLM not initialized: {e}")
    print(" Running in MOCK MODE - responses will be simulated")

class EmailLLMAgent:
    """
    Handles all interactions with the Large Language Model (LLM).
    It takes emails and prompts, constructs the LLM request, and returns structured data.
    """
    def __init__(self, prompt_manager: PromptManager):
        if LLM is None:
             print("WARNING: LLM is not initialized. Mocking responses.")
        
        self.manager = prompt_manager

    def _get_prompt_template(self, prompt_key: str) -> str:
        """Retrieves the template text for a specific prompt key."""
        config = self.manager.get_prompt_config()
        return getattr(config, prompt_key).template

    def process_email_ingestion(self, email_id: int):
        """
        Runs the initial ingestion pipeline: Categorization and Action Extraction.
        """
        email = self.manager.get_email_by_id(email_id)
        if not email:
            print(f"Email ID {email_id} not found.")
            return

        # 1. Categorization
        category = self.categorize_email(email)
        print(f"Email {email_id} categorized as: {category}")
        
        # 2. Action Item Extraction
        action_items = self.extract_action_items(email)
        print(f"Email {email_id} actions: {len(action_items)}")

        # 3. Auto-Drafting
        draft_reply = self.draft_auto_reply(email)
        print(f"Email {email_id} auto-drafted.")

        # 4. Save results to state
        self.manager.save_email_state(
            email_id=email_id,
            category=category,
            action_items=[item.dict() for item in action_items],
            draft_reply=draft_reply
        )

    def categorize_email(self, email: EmailRecord) -> str:
        """Categorizes an email based on the user-defined Categorization Prompt."""
        prompt_template = self._get_prompt_template("Categorization_Prompt")
        
        full_prompt = ChatPromptTemplate.from_template(prompt_template + "\n\nEMAIL CONTENT: {email_body}")

        if LLM:
            chain = full_prompt | LLM | StrOutputParser()
            try:
                result = chain.invoke({"email_body": email.body})
                category = result.strip()
                print(f"✓ Categorized email {email.id}: {category}")
                return category
            except Exception as e:
                print(f"✗ LLM Error during categorization of email {email.id}: {e}")
                # Fall back to mock categorization
                return self._mock_categorize(email)
        else:
            print(f" Using mock categorization for email {email.id}")
            return self._mock_categorize(email)
    
    def _mock_categorize(self, email: EmailRecord) -> str:
        """Mock categorization logic when LLM is unavailable."""
        subject_lower = email.subject.lower()
        body_lower = email.body.lower()
        sender_lower = email.sender.lower()
        
        # Spam detection (HIGHEST PRIORITY - check first)
        spam_indicators = ['pre-approved', 'loan', 'click here immediately', 'act fast', 'social security number', 
                          'unauthorized login', 'suspicious', 'verify your credentials', 'verify your account',
                          'claim your', 'limited time', 'act now', 'you have won']
        if any(word in subject_lower or word in body_lower for word in spam_indicators):
            return "Spam"
        
        # Newsletter detection (CHECK BEFORE TO-DO) - IMPROVED
        newsletter_indicators = [
            # Common newsletter phrases
            'digest', 'newsletter', 'weekly update', 'monthly update', 'last month',
            'unsubscribe', 'view in browser', 'new release', 'announcement',
            'latest news', 'this week', 'tech digest', 'updates include',
            # Update/announcement patterns
            "we've been up to", "excited to share", "here's what", "what we've been",
            "this month's updates", "happy to announce", "check out", "new and improved",
            # Marketing language
            'and much more', 'and more', 'introducing', 'now available',
            # Company update indicators
            'last month', 'this quarter', 'our team', 'we are thrilled'
        ]
        
        newsletter_senders = ['marketing', 'news@', 'newsletter@', 'noreply@', 'updates@', 
                            'hello@', 'team@', 'info@']
        
        # Check both content and sender
        is_newsletter_content = any(word in subject_lower or word in body_lower for word in newsletter_indicators)
        is_newsletter_sender = any(sender in sender_lower for sender in newsletter_senders)
        
        # Strong newsletter signals (must check these specifically)
        if 'informational' in body_lower:
            return "Newsletter"
        if 'unsubscribe' in body_lower or 'view in browser' in body_lower:
            return "Newsletter"
        if "we've been" in body_lower or "excited to share" in body_lower:
            return "Newsletter"
        if "last month" in body_lower and "updates" in body_lower:
            return "Newsletter"
        
        # Important - from directors, CEOs, urgent (check before To-Do)
        if 'urgent' in subject_lower or 'director' in sender_lower or 'ceo' in sender_lower:
            return "Important"
        
       
        # 1. Direct commands/requests
        direct_action_words = [
            'please confirm', 'please send', 'please update', 'please review',
            'need you to', 'can you', 'could you', 'would you',
            'must complete', 'required to', 'action required', 
            'respond by', 'reply by', 'confirm by',
            'task request', 'confirm your', 'send your', 'update your'
        ]
        
        # 2. Meeting/call requests
        meeting_requests = [
            'jump on a call', 'schedule a call', 'quick call', 'can we meet',
            'meeting request', 'let me know if', 'what time works',
            'does this time work', 'are you available', 'schedule a meeting',
            'suggest a time', 'suggest an alternative'
        ]
        
        # 3. Question-based requests
        question_requests = [
            'could we', 'can we', 'would you be able to', 'are you able to',
            'do you have time', 'when can you', 'how soon can you'
        ]
        
        # Check all To-Do patterns
        if any(word in body_lower for word in direct_action_words):
            return "To-Do"
        
        if any(word in body_lower for word in meeting_requests):
            return "To-Do"
            
        if any(word in body_lower for word in question_requests):
            return "To-Do"
        
        # Check subject line for help/action requests
        if any(word in subject_lower for word in ['need help', 'follow-up', 'question about', 'help with']):
            return "To-Do"
        
        # Single action words - only flag as To-Do if combined with urgency/deadline
        if any(word in subject_lower or word in body_lower for word in ['confirm', 'update', 'review', 'complete']):
            # Check if this is actually a request or just informational
            if any(indicator in body_lower for indicator in ['please', 'by eod', 'deadline', 'asap', 'urgent', 'by today', 'by tomorrow']):
                return "To-Do"
        
        # NOW check newsletter patterns (after ruling out To-Do)
        if is_newsletter_content or is_newsletter_sender:
            return "Newsletter"
        
        # Policy updates, status updates, company announcements = Newsletter
        if any(word in subject_lower or word in body_lower for word in 
               ['policy change', 'status update', 'no action', 'company-wide', 'fyi', 'for your information']):
            return "Newsletter"
        
        # Default to Newsletter for informational content
        return "Newsletter"

    def extract_action_items(self, email: EmailRecord) -> List[ActionItem]:
        """Extracts structured action items using the user-defined Action Extraction Prompt."""
        prompt_template = self._get_prompt_template("Action_Extraction_Prompt")
        
        parser = JsonOutputParser(pydantic_object=ActionItemList)
        format_instructions = parser.get_format_instructions()

        full_prompt = ChatPromptTemplate.from_template(
            prompt_template + "\n\nEMAIL CONTENT: {email_body}\n\n{format_instructions}"
        )

        if LLM:
            chain = full_prompt | LLM | parser
            try:
                result_wrapper = chain.invoke({
                    "email_body": email.body,
                    "format_instructions": format_instructions
                })
                result_list_of_dicts = result_wrapper.get('action_items', [])
                actions = [ActionItem(**item) for item in result_list_of_dicts]
                print(f"✓ Extracted {len(actions)} action items from email {email.id}")
                return actions
            except Exception as e:
                print(f"✗ LLM Error during action extraction of email {email.id}: {e}")
                return self._mock_extract_actions(email)
        else:
            print(f"⚠ Using mock action extraction for email {email.id}")
            return self._mock_extract_actions(email)
    
    def _mock_extract_actions(self, email: EmailRecord) -> List[ActionItem]:
        """Mock action extraction when LLM is unavailable."""
        actions = []
        subject_lower = email.subject.lower()
        body_lower = email.body.lower()
        
        # Check for specific action keywords
        if "confirm" in subject_lower or "confirm" in body_lower:
            actions.append(ActionItem(
                task=f"Confirm attendance/action for: {email.subject}",
                deadline="EOD today" if "eod" in body_lower else "ASAP"
            ))
        
        if "update" in subject_lower or "complete" in body_lower:
            deadline = "Wednesday morning" if "wednesday" in body_lower else "None"
            actions.append(ActionItem(
                task=f"Complete task: {email.subject}",
                deadline=deadline
            ))
        
        if "review" in subject_lower or "review" in body_lower:
            actions.append(ActionItem(
                task=f"Review and respond to: {email.subject}",
                deadline="None"
            ))
        
        if "meeting" in subject_lower or "invitation" in subject_lower:
            actions.append(ActionItem(
                task=f"Respond to meeting invitation: {email.subject}",
                deadline="ASAP"
            ))
        
        if "invoice" in subject_lower or "payment" in body_lower:
            deadline = "Friday" if "friday" in body_lower else "Next week"
            actions.append(ActionItem(
                task=f"Process payment for: {email.subject}",
                deadline=deadline
            ))
        
        return actions

    def draft_auto_reply(self, email: EmailRecord) -> str:
        """Drafts a reply based on the Auto-Reply Draft Prompt."""
        prompt_template = self._get_prompt_template("Auto_Reply_Prompt")

        full_prompt = ChatPromptTemplate.from_template(prompt_template + "\n\nEMAIL CONTENT: {email_body}")

        if LLM:
            chain = full_prompt | LLM | StrOutputParser()
            try:
                draft_text = chain.invoke({"email_body": email.body})
                print(f"✓ Drafted reply for email {email.id}")
                return draft_text.strip()
            except Exception as e:
                print(f"✗ LLM Error during reply drafting of email {email.id}: {e}")
                return self._mock_draft_reply(email)
        else:
            print(f"⚠ Using mock draft for email {email.id}")
            return self._mock_draft_reply(email)
    
    def _mock_draft_reply(self, email: EmailRecord) -> str:
        """Mock reply drafting when LLM is unavailable."""
        subject_lower = email.subject.lower()
        body_lower = email.body.lower()
        
        # Meeting requests
        if any(word in subject_lower or word in body_lower for word in 
               ['meeting', 'invitation', 'schedule', 'call', 'sync', 'brainstorm']):
            return "Thank you for the invitation. Could you please send a brief agenda or purpose for this meeting? I'd like to come prepared. Looking forward to it!"
        
        # Task requests
        if any(word in subject_lower for word in ['task request', 'update', 'review']):
            return "Thank you for reaching out. I've received your request and will look into this. I'll get back to you with an update soon."
        
        # Questions
        if 'question' in subject_lower or '?' in body_lower:
            return "Thanks for your question. Let me review this and get back to you with a detailed response shortly."
        
        # Default for spam/newsletter - no reply
        if any(word in subject_lower or word in body_lower for word in 
               ['newsletter', 'digest', 'unsubscribe', 'pre-approved']):
            return ""
        
        # Generic acknowledgment
        return "Thank you for your email. I've received it and will respond accordingly."

    def handle_chat_query(self, user_query: str, email_id: int = None) -> str:
        """
        Handles complex chat queries, combining user instruction, email context, and system prompts.
        """
        email_context = ""
        if email_id is not None:
            email = self.manager.get_email_by_id(email_id)
            if email:
                email_context = f"\n\n--- SELECTED EMAIL CONTENT ---\nSubject: {email.subject}\nBody: {email.body}"
                
                if "draft a reply" in user_query.lower():
                    draft = self.draft_auto_reply(email)
                    return f"**Draft Generated:**\n\n{draft}"
                
                if "summarize" in user_query.lower():
                    system_prompt = "You are a helpful assistant. Summarize the following email concisely."
                
                elif "tasks" in user_query.lower():
                    items = email.action_items
                    if items:
                        task_list_parts = []
                        for item in items:
                            if isinstance(item, ActionItem):
                                task_list_parts.append(f"- {item.task} (Deadline: {item.deadline})")
                            elif isinstance(item, dict):
                                task_list_parts.append(f"- {item.get('task', 'Unknown')} (Deadline: {item.get('deadline', 'None')})")
                            else:
                                task_list_parts.append(f"- {str(item)}")
                        
                        task_list = "\n".join(task_list_parts)
                        return f"The extracted tasks from this email are:\n{task_list}"
                    else:
                        return "No specific action items were extracted for this email."
        
        if "show me all" in user_query.lower() or "urgent emails" in user_query.lower():
            target_category = "Important" if "urgent" in user_query.lower() else "To-Do"
            
            filtered_emails = [e for e in self.manager.get_emails() if e.category == target_category]
            
            if filtered_emails:
                summary = f"Found {len(filtered_emails)} emails categorized as **{target_category}**:\n"
                summary += "\n".join([f"- ID {e.id}: {e.subject}" for e in filtered_emails])
                return summary
            else:
                return f"No emails currently categorized as **{target_category}**."

        final_prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are an intelligent Email Agent. Use the provided email content to answer the user's question. If no email is provided, answer generally."),
            ("user", user_query + email_context)
        ])

        if LLM:
            chain = final_prompt_template | LLM | StrOutputParser()
            try:
                result = chain.invoke({"user_query": user_query, "email_context": email_context})
                return result.strip()
            except Exception as e:
                print(f"LLM Error during chat handling: {e}")
                return "Sorry, I encountered an error while processing your request."
        else:
            return f"Mock response for query: '{user_query}'. If email ID {email_id} was selected, it was used as context."