import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from core.prompt_manager import PromptManager
from core.llm_agent import EmailLLMAgent
from core.models import EmailRecord
from typing import List, Dict
from datetime import datetime 

# --- 0. Initialization and State Management ---

@st.cache_resource
def load_manager_and_agent():
    """Load the PromptManager and EmailLLMAgent once."""
    try:
        manager = PromptManager()
        agent = EmailLLMAgent(manager)
        return manager, agent
    except Exception as e:
        st.error(f"Error during initialization: {e}")
        st.stop()

if 'manager' not in st.session_state:
    st.session_state['manager'], st.session_state['agent'] = load_manager_and_agent()
    st.session_state['selected_email_id'] = None
    st.session_state['chat_history'] = []

manager: PromptManager = st.session_state['manager']
agent: EmailLLMAgent = st.session_state['agent']

# --- KEYBOARD SHORTCUTS - Working Implementation ---
keyboard_script = """
<script>
const doc = window.parent.document;

doc.addEventListener('keydown', function(e) {
    // Ignore if typing in input/textarea
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
    }
    
    const key = e.key.toLowerCase();
    
    if (key === 'p') {
        e.preventDefault();
        e.stopPropagation();
        // Trigger process action
        const buttons = doc.querySelectorAll('button');
        buttons.forEach(btn => {
            if (btn.innerText.includes('Run Ingestion Pipeline')) {
                btn.click();
            }
        });
    }
    
    if (key === 'i') {  // Changed from 'c' to 'i' for Inbox
        e.preventDefault();
        e.stopPropagation();
        // Switch to inbox tab (1st tab)
        const tabs = doc.querySelectorAll('[role="tab"]');
        if (tabs[0]) tabs[0].click();
    }
    
    if (key === 'a') {  // Changed from 'c' to 'a' for Agent chat
        e.preventDefault();
        e.stopPropagation();
        // Switch to chat tab (2nd tab)
        const tabs = doc.querySelectorAll('[role="tab"]');
        if (tabs[1]) tabs[1].click();
    }
    
    if (key === 'd') {
        e.preventDefault();
        e.stopPropagation();
        // Switch to dashboard tab (3rd tab)
        const tabs = doc.querySelectorAll('[role="tab"]');
        if (tabs[2]) tabs[2].click();
    }
}, true);  // Added 'true' for capture phase to intercept before Streamlit
</script>
"""

components.html(keyboard_script, height=0)

# --- CSS Fix (Removing glitching tab styles and using consistent colors) ---
st.markdown("""
<style>
    /* Tabs FIX: Removed background gradient to fix purple box glitch */
    .stTabs [data-baseweb="tab-list"] {
        border-radius: 10px;
        padding: 0.5rem;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff; 
        color: black !important;
        border-radius: 8px;
    }
    
    /* General Styling */
    h1, h2, h3 { color: #4A4A4A !important; font-weight: 600; }
    .stButton>button {
        background: linear-gradient(135deg, #6495ED 0%, #1E90FF 100%); 
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(30, 144, 255, 0.3); 
    }
    .stInfo, .stWarning { border-left: 4px solid #4682B4; } 
    
    /* Keyword tags style */
    .keyword-tag {
        display: inline-block;
        background: linear-gradient(135deg, #6495ED 0%, #1E90FF 100%);
        color: white;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        margin: 0.3rem;
        font-size: 0.9rem;
        font-weight: 500;
    }

    /* Removed .keyword-box and .keyword-display-container styling */
</style>
""", unsafe_allow_html=True)

# --- 1. Helper Functions ---

def run_ingestion_pipeline():
    """Processes all emails using the LLM Agent."""
    with st.spinner('Processing emails with LLM...'):
        emails = manager.get_emails()
        # Ensure we always reload the mock data on ingestion start to reset category/actions
        manager._load_emails()
        for email in emails:
            agent.process_email_ingestion(email.id)
    st.success("Ingestion complete! Emails are categorized and action items extracted.")

def display_email_list(emails: List[EmailRecord]):
    """Displays the list of emails in a clear, interactive format."""
    data = [{
        'ID': e.id,
        'Sender': e.sender,
        'Subject': e.subject,
        'Timestamp': e.timestamp[:16].replace('T', ' '),
        'Category': e.category if e.category else 'Unprocessed'
    } for e in emails]

    df = pd.DataFrame(data)
    
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_order=['ID', 'Category', 'Sender', 'Subject', 'Timestamp'],
        column_config={
            "ID": st.column_config.NumberColumn(width="small"),
            "Category": st.column_config.Column(width="small"),
        }
    )
    
    selected_subject = st.selectbox(
        "Select an Email to View or Chat",
        options=[''] + [f"{e.id}: {e.subject}" for e in emails],
        index=0,
        key='email_selector'
    )

    if selected_subject:
        email_id = int(selected_subject.split(':')[0])
        st.session_state['selected_email_id'] = email_id
        st.success(f"Email {email_id} selected! Go to the 'Email Agent Chat' tab to interact with it.")

# --- 2. UI Layout ---

st.title("Email Productivity Agent")
st.caption("Hi there! Let's get going")

# Tabs
tab_inbox, tab_viewer, tab_dashboard, tab_prompts = st.tabs([
    "Inbox & Ingestion", 
    "Email Agent Chat", 
    "Priority Dashboard", 
    "Customize Prompts"
])

with tab_inbox:
    st.header("Inbox Management")
    
    st.markdown("### Email Source")
    col1, col2 = st.columns([1, 1.5])

    with col1:
        # Disabled button for future feature
        st.button(
            "Connect Gmail Account", 
            type="secondary",
            disabled=True, 
            help="Gmail integration coming soon! Currently using mock data."
        )
        st.caption("Demo Mode: Feature disabled.")

    with col2:
        # Load Mock Inbox button
        if st.button("Load Mock Inbox", type="primary"):
            manager._load_emails()
            st.success("Mock Inbox loaded. Ready to process!")
            
    # Processing Button
    st.button("3. Run Ingestion Pipeline (Categorize & Extract)", on_click=run_ingestion_pipeline, type="secondary")
    
    st.divider()

    # Informational expander about future Gmail integration
    with st.expander("About Gmail Integration (Future Feature)", expanded=False):
        st.markdown("""
        ### Planned Gmail Integration
        
        **What it will do:**
        - Connect to your real Gmail account via OAuth 2.0
        - Fetch latest 50 emails from inbox
        - Support filters (unread, starred, from specific senders)
        - Real-time sync with Gmail labels
        
        **Technical Implementation:**
        - Google Gmail API with OAuth 2.0
        - Scopes: `gmail.readonly`, `gmail.modify`
        - Secure token storage in session state
        
        **Why it's not live yet:**
        This demo uses mock data to ensure consistent results during evaluation. In production, OAuth credentials and deployment security would be required.
        """)
    
    st.divider()
    display_email_list(manager.get_emails())

with tab_viewer:
    st.header("Email Agent Chat")
    
    if st.session_state['selected_email_id'] is None:
        st.info("Please select an email from the Inbox & Ingestion tab first.")
    else:
        email_id = st.session_state['selected_email_id']
        email = manager.get_email_by_id(email_id)
        
        if email:
            st.markdown(f"### Email: {email.subject}")
            st.markdown(f"**From:** `{email.sender}` | **Category:** `{email.category}` | **Time:** `{email.timestamp[:16]}`")
            st.divider()
            
            col1, col2 = st.columns([1.2, 1])
            
            with col1:
                st.subheader("Email Body")
                st.markdown(f"> {email.body}")
            
            with col2:
                st.subheader("Agent Outputs")
                
                st.markdown("**Action Items**")
                if email.action_items:
                    for idx, item in enumerate(email.action_items):
                        if hasattr(item, 'task'):
                            st.markdown(f"{idx+1}. Task: {item.task}")
                            st.markdown(f"   Deadline: {item.deadline}")
                        elif isinstance(item, dict):
                            st.markdown(f"{idx+1}. Task: {item.get('task', 'Unknown')}")
                            st.markdown(f"   Deadline: {item.get('deadline', 'None')}")
                else:
                    st.info("No action items extracted.")
                
                st.divider()
                
                st.markdown("**Auto-Draft Reply**")
                if email.draft_reply:
                    st.text_area("Generated Draft", email.draft_reply, height=150, key="draft_display")
                else:
                    st.warning("No auto-draft generated yet.")
            
            st.divider()
            st.subheader("Chat with Agent")
            st.markdown("Ask questions about this email or request actions:")
            
            for message in st.session_state['chat_history']:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input("Ask: 'What tasks do I need?', 'Summarize this', 'Draft a reply'..."):
                st.session_state['chat_history'].append({"role": "user", "content": prompt})

                with st.chat_message("user"):
                    st.markdown(prompt)

                with st.spinner("Agent is thinking..."):
                    try:
                        response = agent.handle_chat_query(prompt, email_id)
                    except Exception as e:
                        response = f"Error: {str(e)}\n\nPlease try again or contact support."
                        st.error(f"Chat error: {e}")
                
                with st.chat_message("assistant"):
                    st.markdown(response)
                    st.session_state['chat_history'].append({"role": "assistant", "content": response})
        else:
            st.error("Selected email not found. Please go back and select another email.")

with tab_dashboard:
    st.header("Priority Dashboard")
    st.markdown("All your emails organized by priority and deadline")
    st.divider()
    
    # Collect data for dashboard
    emails = manager.get_emails()
    all_tasks = []
    for email in emails:
        if email.action_items:
            for item in email.action_items:
                task_data = {
                    'email_id': email.id,
                    'sender': email.sender,
                    'email_subject': email.subject,
                    'category': email.category,
                    'timestamp': email.timestamp
                }
                if isinstance(item, dict):
                    task_data['task'] = item.get('task', 'Unknown')
                    task_data['deadline'] = item.get('deadline', 'None')
                else:
                    task_data['task'] = item.task
                    task_data['deadline'] = item.deadline
                all_tasks.append(task_data)

    # Filter tasks
    deadline_tasks = [t for t in all_tasks if t['deadline'] != 'None']
    important_emails = [e for e in emails if e.category == "Important"]
    todo_emails = [e for e in emails if e.category == "To-Do"]

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Tasks", len(all_tasks))
    with col2:
        st.metric("Important Emails", len(important_emails))
    with col3:
        st.metric("To-Do Emails", len(todo_emails))
    with col4:
        st.metric("Tasks with Deadline", len(deadline_tasks))
    
    st.divider()
    
    # Focused Dashboard Structure
    st.subheader("Urgent and Time-Sensitive Tasks")
    
    if deadline_tasks:
        for idx, task in enumerate(deadline_tasks):
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{task['task']}**")
                    st.caption(f"Deadline: {task['deadline']} | From: {task['email_subject']}")
                with col2:
                    if st.button("View Email", key=f"view_task_{idx}"):
                        st.session_state['selected_email_id'] = task['email_id']
                        st.info("Email selected. Go to Email Agent Chat tab.")
    else:
        st.info("No time-sensitive tasks found.")
    
    st.divider()
    
    st.subheader("General To-Do Emails")
    if todo_emails:
        for email in todo_emails:
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**{email.subject}**")
                    st.caption(f"From: {email.sender}")
                with col2:
                    if st.button("View", key=f"view_todo_{email.id}"):
                        st.session_state['selected_email_id'] = email.id
                        st.info("Email selected. Go to Email Agent Chat tab.")
    else:
        st.info("No general to-do emails.")
    
    st.divider()
    
    st.subheader("Informational / Spam")
    newsletter_emails = [e for e in emails if e.category == "Newsletter"]
    spam_emails = [e for e in emails if e.category == "Spam"]
    
    if newsletter_emails or spam_emails:
        with st.expander(f"Show {len(newsletter_emails) + len(spam_emails)} low priority items"):
            for email in newsletter_emails:
                st.markdown(f"[Newsletter] {email.subject} - {email.sender}")
                st.caption(email.timestamp[:16])
                st.divider()
            for email in spam_emails:
                st.markdown(f"[Spam] {email.subject} - {email.sender}")
                st.caption(email.timestamp[:16])
                st.divider()
    else:
        st.info("No low priority emails.")

with tab_prompts:
    st.header("Prompt Configuration")
    st.markdown("Customize how emails are categorized without writing prompts")
    st.divider()
    
    # Initialize category keywords in session state
    if 'category_keywords' not in st.session_state:
        st.session_state['category_keywords'] = {
            'Important': [],
            'Spam': [],
            'Newsletter': [],
            'To-Do': []
        }
    
    # Categorization Section
    with st.expander("Categorization (Categorization_Prompt)", expanded=True):
        st.markdown("**Description:** Guides the LLM on how to classify emails into operational tags.")
        st.markdown("**Expected Output:** text")
        
        st.markdown("### Add Keywords for Each Category")
        st.caption("Enter keywords that should trigger each category. The agent will use these to classify emails.")
        
        # Create 4 columns for keyword boxes - TWO ROWS
        # Row 1: Important and Spam
        col1, col2 = st.columns(2)
        
        # Row 2: Newsletter and To-Do
        col3, col4 = st.columns(2)
        
        
        categories_config = [
            ('Important', col1),
            ('Spam', col2),
            ('Newsletter', col3),
            ('To-Do', col4)
        ]
        
        for category, column in categories_config:
            with column:
                
                # Category Title at the top
                st.markdown(f"### {category}")
                
                # Display existing keywords directly below the title
                key_prefix = f"{category}_cat"
                if key_prefix not in st.session_state:
                    st.session_state[key_prefix] = []
                
                # Show keywords as tags or the 'No keywords added yet' message
                if st.session_state[key_prefix]:
                    keywords_html = "".join([
                        f"<span class='keyword-tag'>{kw}</span>" 
                        for kw in st.session_state[key_prefix]
                    ])
                    st.markdown(keywords_html, unsafe_allow_html=True)
                else:
                    # Using standard markdown for the 'No keywords added yet' message, slightly styled for clarity
                    st.markdown(f'<p style="color: #6c757d; font-style: italic; margin-bottom: 1rem;">No keywords added yet</p>', unsafe_allow_html=True)
                
                # Input for new keyword
                new_keyword = st.text_input(
                    "Add keyword",
                    key=f"input_{key_prefix}",
                    placeholder=f"e.g., {category.lower()} keywords",
                    label_visibility="collapsed"
                )
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Add", key=f"add_{key_prefix}"):
                        if new_keyword and new_keyword not in st.session_state[key_prefix]:
                            st.session_state[key_prefix].append(new_keyword.lower())
                            st.rerun()
                
                with col_b:
                    if st.button("Clear All", key=f"clear_{key_prefix}"):
                        st.session_state[key_prefix] = []
                        st.rerun()
                
        
        st.divider()
        
        # Generate and save button
        if st.button("Save Categorization Prompt", type="primary"):
            # Generate prompt from keywords
            generated_prompt = "Analyze the following email and categorize it using one of: 'Important', 'Newsletter', 'Spam', or 'To-Do'.\n\n"
            
            if st.session_state.get('Important_cat'):
                keywords = ', '.join(st.session_state['Important_cat'])
                generated_prompt += f"Mark as Important if contains: {keywords}\n"
            
            if st.session_state.get('Spam_cat'):
                keywords = ', '.join(st.session_state['Spam_cat'])
                generated_prompt += f"Mark as Spam if contains: {keywords}\n"
            
            if st.session_state.get('Newsletter_cat'):
                keywords = ', '.join(st.session_state['Newsletter_cat'])
                generated_prompt += f"Mark as Newsletter if contains: {keywords}\n"
            
            if st.session_state.get('To-Do_cat'):
                keywords = ', '.join(st.session_state['To-Do_cat'])
                generated_prompt += f"Mark as To-Do if contains: {keywords}\n"
            
            generated_prompt += "\nRespond with ONLY the category name."
            
            # Save to manager
            if manager.update_prompt_template('Categorization_Prompt', generated_prompt):
                st.success("Categorization Prompt updated! Rerun ingestion to apply changes.")
            else:
                st.error("Failed to save prompt.")
    
    # Action Extraction Section
    with st.expander("Action Item Extraction (Action_Extraction_Prompt)", expanded=False):
        st.markdown("**Description:** Guides the LLM on extracting structured tasks and deadlines.")
        st.markdown("**Expected Output:** json")
        
        prompts_config = manager.get_prompt_config()
        template = prompts_config.Action_Extraction_Prompt.template
        
        new_template = st.text_area(
            "Edit Template:",
            value=template,
            height=200,
            key="template_action"
        )
        
        if st.button("Save Action Extraction Prompt"):
            if manager.update_prompt_template('Action_Extraction_Prompt', new_template):
                st.success("Prompt updated! Rerun ingestion to apply changes.")
    
    # Auto-Reply Section
    with st.expander("Auto-Reply Draft (Auto_Reply_Prompt)", expanded=False):
        st.markdown("**Description:** Guides the LLM on generating situational draft replies.")
        st.markdown("**Expected Output:** text")
        
        prompts_config = manager.get_prompt_config()
        template = prompts_config.Auto_Reply_Prompt.template
        
        new_template = st.text_area(
            "Edit Template:",
            value=template,
            height=200,
            key="template_reply"
        )
        
        if st.button("Save Auto-Reply Prompt"):
            if manager.update_prompt_template('Auto_Reply_Prompt', new_template):
                st.success("Prompt updated! Rerun ingestion to apply changes.")

# Sidebar
st.sidebar.markdown("### Quick Start Guide")
st.sidebar.markdown("1. Load data (Mock or Gmail)")
st.sidebar.markdown("2. Run Ingestion Pipeline")
st.sidebar.markdown("3. View Priority Dashboard for action items")
st.sidebar.markdown("4. Use Email Agent Chat for summaries/drafts")

st.sidebar.divider()
st.sidebar.markdown("### Keyboard Shortcuts")
st.sidebar.markdown("- **P** - Process emails")
st.sidebar.markdown("- **I** - Inbox tab")
st.sidebar.markdown("- **A** - Agent chat tab")
st.sidebar.markdown("- **D** - Dashboard tab")
st.sidebar.caption("Press keys when not typing in input fields")

st.sidebar.divider()

if st.sidebar.button("Clear Chat History"):
    st.session_state['chat_history'] = []
    st.rerun()