import streamlit as st
import pandas as pd
from core.prompt_manager import PromptManager
from core.llm_agent import EmailLLMAgent
from core.models import EmailRecord
from typing import List, Dict



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




def run_ingestion_pipeline():
    """Processes all emails using the LLM Agent."""
    with st.spinner('Processing emails with LLM...'):
        emails = manager.get_emails()
        for email in emails:
            # Runs Categorization, Action Extraction, and Auto-Reply Drafting
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
    
    # Use Streamlit's dataframe feature for better interaction
    st.dataframe(
        df,
        # Fixing deprecated 'use_container_width' warning (though it's still in the source file)
        width='stretch', 
        hide_index=True,
        column_order=['ID', 'Category', 'Sender', 'Subject', 'Timestamp'],
        column_config={
            "ID": st.column_config.NumberColumn(width="small"),
            "Category": st.column_config.Column(width="small"),
        }
    )
    
    # Allow selection of an email for viewing/chat
    selected_subject = st.selectbox(
        "**Select an Email to View or Chat**", 
        options=[''] + [f"{e.id}: {e.subject}" for e in emails],
        index=0,
        key='email_selector'
    )

    if selected_subject:
        email_id = int(selected_subject.split(':')[0])
        st.session_state['selected_email_id'] = email_id
        st.success(f" Email {email_id} selected! Go to the 'Email Agent Chat' tab to interact with it.")




st.set_page_config(layout="wide", page_title="Prompt-Driven Email Agent")
st.title(" Prompt-Driven Email Productivity Agent")
st.caption("Backend Architecture: Python/Pydantic/LLM Agent | Frontend: Streamlit")

# Use tabs to separate the main components
tab_inbox, tab_viewer, tab_calendar, tab_prompts = st.tabs([" Inbox & Ingestion", " Email Agent Chat", " Calendar & Tasks", " Customize Prompt"])

with tab_inbox:
    st.header(" Inbox Management")
    st.button("Load Mock Inbox & Run Ingestion Pipeline", on_click=run_ingestion_pipeline, type="primary")
    st.divider()
    
    # Display the email list
    display_email_list(manager.get_emails())

with tab_viewer:
    st.header(" Email Agent Chat")
    
    # Check if an email is selected
    if st.session_state['selected_email_id'] is None:
        st.info(" Please select an email from the **Inbox & Ingestion** tab first.")
        st.markdown("### How to use:")
        st.markdown("1. Go to the **Inbox & Ingestion** tab")
        st.markdown("2. Click **Load Mock Inbox & Run Ingestion Pipeline**")
        st.markdown("3. Select an email from the dropdown")
        st.markdown("4. Come back to this tab to chat!")
    else:
        email_id = st.session_state['selected_email_id']
        email = manager.get_email_by_id(email_id)
        
        if email:
            # Display email header
            st.markdown(f"###  Email: {email.subject}")
            st.markdown(f"**From:** `{email.sender}` | **Category:** `{email.category}` | **Time:** `{email.timestamp[:16]}`")
            st.divider()
            
            # Two columns Email content and Agent outputs
            col1, col2 = st.columns([1.2, 1])
            
            with col1:
                st.subheader(" Email Body")
                st.markdown(f"> {email.body}")
            
            with col2:
                st.subheader(" Agent Outputs")
                
                # Display Action Items
                st.markdown("** Action Items**")
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
                
                # Display Draft Reply
                st.markdown("** Auto-Draft Reply**")
                if email.draft_reply:
                    st.text_area("Generated Draft", email.draft_reply, height=150, key="draft_display")
                else:
                    st.warning("No auto-draft generated yet.")
            
            st.divider()
            st.subheader(" Chat with Agent")
            st.markdown("Ask questions about this email or request actions:")
            
            # Display chat history
            for message in st.session_state['chat_history']:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Chat input
            if prompt := st.chat_input("Ask: 'What tasks do I need?', 'Summarize this', 'Draft a reply'..."):
                # Add user message to history
                st.session_state['chat_history'].append({"role": "user", "content": prompt})

                with st.chat_message("user"):
                    st.markdown(prompt)

                # Get agent response
                with st.spinner(" Agent is thinking..."):
                    try:
                        response = agent.handle_chat_query(prompt, email_id)
                    except Exception as e:
                        response = f" Error: {str(e)}\n\nPlease try again or contact support."
                        st.error(f"Chat error: {e}")
                
                # Add assistant response to history
                with st.chat_message("assistant"):
                    st.markdown(response)
                    st.session_state['chat_history'].append({"role": "assistant", "content": response})
        else:
            st.error(" Selected email not found. Please go back and select another email.")


with tab_calendar:
    st.header("Calendar & Task Manager")
    st.markdown("View all extracted tasks and export them to your calendar app.")
    st.divider()
    
    # Collect all tasks again
    all_tasks = []
    for email in manager.get_emails():
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
    
    if all_tasks:
        # Summary cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Tasks", len(all_tasks))
        with col2:
            urgent = len([t for t in all_tasks if t['category'] == "Important"])
            st.metric("Important", urgent)
        with col3:
            todo = len([t for t in all_tasks if t['category'] == "To-Do"])
            st.metric("To-Do", todo)
        with col4:
            with_deadline = len([t for t in all_tasks if t['deadline'] != "None"])
            st.metric("With Deadline", with_deadline)
        
        st.divider()
        
        # Filter by category
        filter_cat = st.selectbox(
            "Filter by Category:",
            ["All", "Important", "To-Do", "Newsletter", "Spam"]
        )
        
        # Apply filter
        if filter_cat != "All":
            filtered = [t for t in all_tasks if t['category'] == filter_cat]
        else:
            filtered = all_tasks
        
        st.markdown(f"### Showing {len(filtered)} tasks")
        
        # Display tasks in a nice format
        for idx, task in enumerate(filtered):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                # Task card
                deadline_icon = "" if task['deadline'] != "None" else ""
                category_color = {
                    "Important": "",
                    "To-Do": "",
                    "Newsletter": "",
                    "Spam": ""
                }.get(task['category'], "")
                
                st.markdown(f"""
                **{deadline_icon} Task {idx+1}** {category_color} `{task['category']}`
                
                **Task:** {task['task']}
                
                **From Email:** {task['email_subject']} (ID: {task['email_id']})
                
                **Sender:** {task['sender']}
                
                ** Deadline:** `{task['deadline']}`
                """)
            
            with col2:
                from datetime import datetime
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Calendar export
                ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Email Agent//Task//EN
BEGIN:VEVENT
UID:task-{task['email_id']}-{idx}@emailagent
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}
SUMMARY:{task['task'][:75]}
DESCRIPTION:From: {task['sender']}\\n\\nEmail: {task['email_subject']}\\n\\nDeadline: {task['deadline']}\\n\\nCategory: {task['category']}
STATUS:CONFIRMED
PRIORITY:{1 if task['category'] == 'Important' else 5}
END:VEVENT
END:VCALENDAR"""
                
                st.download_button(
                    label="📅 Add to Calendar",
                    data=ics_content,
                    file_name=f"task_{task['email_id']}_{idx}.ics",
                    mime="text/calendar",
                    key=f"calendar_export_{idx}",
                    help="Download .ics file to import into Google Calendar, Outlook, or Apple Calendar"
                )
                
                # Mark as done (visual only for now)
                if st.button(" Mark Done", key=f"mark_done_{idx}"):
                    st.success("Task marked as complete!")
                
                # View email button
                if st.button("View Email", key=f"view_email_{idx}"):
                    st.session_state['selected_email_id'] = task['email_id']
                    st.info(f"Email #{task['email_id']} selected. Go to 'Email Agent Chat' tab.")
            
            st.divider()
        
        st.divider()
        st.markdown("### Calendar Export")
        st.markdown("Export all tasks at once:")
        
        # Generate bulk .ics file
        from datetime import datetime
        bulk_ics = "BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//Email Agent//Tasks//EN\n"
        
        for idx, task in enumerate(filtered):
            bulk_ics += f"""BEGIN:VEVENT
UID:bulk-task-{task['email_id']}-{idx}@emailagent
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}
SUMMARY:{task['task'][:75]}
DESCRIPTION:From: {task['sender']}\\n\\nEmail: {task['email_subject']}\\n\\nDeadline: {task['deadline']}
STATUS:CONFIRMED
PRIORITY:{1 if task['category'] == 'Important' else 5}
END:VEVENT
"""
        
        bulk_ics += "END:VCALENDAR"
        
        st.download_button(
            label=f"⬇️ Download All {len(filtered)} Tasks as Calendar File",
            data=bulk_ics,
            file_name="all_tasks.ics",
            mime="text/calendar",
            type="primary"
        )
        
        st.info(" **Tip:** After downloading, open the .ics file with your calendar app (Google Calendar, Outlook, Apple Calendar) to import all tasks at once!")
        
    else:
        st.info(" No tasks found yet. Go to the **Inbox & Ingestion** tab and click 'Load Mock Inbox & Run Ingestion Pipeline' first!")
        st.markdown("### How Calendar Export Works:")
        st.markdown("""
        1. Process emails to extract tasks
        2. Click "Add to Calendar" on any task
        3. Download the .ics calendar file
        4. Import into:
           - **Google Calendar**: Settings → Import & Export → Import
           - **Outlook**: File → Open & Export → Import/Export
           - **Apple Calendar**: File → Import
        5. Tasks appear as calendar events with deadlines!
        """)

with tab_prompts:
    st.header("Prompt Configuration")
    st.markdown("Edit these templates to change the core behavior of the LLM Agent")
    st.divider()

    prompts_config = manager.get_prompt_config()
    
    # Use an expander for each prompt for a cleaner UI
    for key, prompt_obj in prompts_config.dict().items():
        with st.expander(f"**{prompt_obj['name']}** ({key})", expanded=False):
            st.markdown(f"**Description:** {prompt_obj['description']}")
            st.markdown(f"**Expected Output:** `{prompt_obj['output_format']}`")
            
            # Text area for editing the template
            new_template = st.text_area(
                f"Edit Template for {prompt_obj['name']}:",
                value=prompt_obj['template'],
                height=250,
                key=f"template_{key}"
            )
            
            if st.button(f"Save '{prompt_obj['name']}' Prompt", key=f"save_button_{key}"):
                if manager.update_prompt_template(key, new_template):
                    st.success(f"Prompt '{prompt_obj['name']}' successfully updated in memory. Rerun ingestion to see changes!")
                else:
                    st.error("Failed to save prompt. Check console for details.")


# We will define the order of the two main sidebar sections in session state
if 'sidebar_order' not in st.session_state:
    st.session_state['sidebar_order'] = ['tasks', 'guide']

# Function to render the Task Dashboard
def render_task_dashboard():
    
    with st.sidebar.expander("## Task Dashboard", expanded=True):
        st.markdown(f"### {len(all_tasks)} Total Tasks Found") 
        
        # Filter options
        filter_option = st.radio(
            "Show tasks from:",
            ["All Emails", "Important Only", "To-Do Only", "Selected Email Only"],
            index=0,
            key='task_filter_sidebar'
        )
        
        # Apply filter
        all_tasks_copy = all_tasks.copy() 
        filtered_tasks = all_tasks_copy
        if filter_option == "Important Only":
            filtered_tasks = [t for t in all_tasks_copy if t['category'] == "Important"]
        elif filter_option == "To-Do Only":
            filtered_tasks = [t for t in all_tasks_copy if t['category'] == "To-Do"]
        elif filter_option == "Selected Email Only" and st.session_state['selected_email_id']:
            filtered_tasks = [t for t in all_tasks_copy if t['email_id'] == st.session_state['selected_email_id']]
        
        st.divider()
        
        # Display tasks
        if filtered_tasks:
            for idx, task in enumerate(filtered_tasks):
                # Inner Expander for individual task details
                with st.expander(f"Task {idx+1} ({task['category']})", expanded=False):
                    st.markdown(f"**From:** {task['email_subject'][:40]}...")
                    st.markdown(f"**Task:** {task['task']}")
                    st.markdown(f"**Deadline:** `{task['deadline']}`")
                    
                    # Calendar/Done buttons
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Calendar", key=f"cal_{idx}_sidebar"):
                            st.toast("Go to 'Calendar & Tasks' tab for export!", icon="✅")
                    
                    with col2:
                        if st.button("Done", key=f"done_{idx}_sidebar"):
                            st.toast("Task marked as done!", icon="✅")
        else:
            st.info("No tasks matched the current filter.")

# Function to render the Quick Start Guide
def render_quick_start_guide():
   
    with st.sidebar.expander("## Quick Start Guide", expanded=True):
        st.markdown("1. Go to **Inbox & Ingestion** tab")
        st.markdown("2. Click **Load Mock Inbox**")
        st.markdown("3. Select an email from dropdown")
        st.markdown("4. Go to **Email Agent Chat** tab")
        st.divider()
        st.markdown("### Chat Examples")
        st.markdown("- *What tasks do I need?*")
        st.markdown("- *Summarize this email*")
        st.markdown("- *Draft a reply*")


all_tasks = []
for email in manager.get_emails():
    if email.action_items:
        for item in email.action_items:
            task_data = {
                'email_id': email.id,
                'email_subject': email.subject,
                'category': email.category
            }
            if isinstance(item, dict):
                task_data['task'] = item.get('task', 'Unknown')
                task_data['deadline'] = item.get('deadline', 'None')
            else:
                task_data['task'] = item.task
                task_data['deadline'] = item.deadline
            all_tasks.append(task_data)

# Function to toggle the order
def toggle_sidebar_order():
    if st.session_state['sidebar_order'] == ['tasks', 'guide']:
        st.session_state['sidebar_order'] = ['guide', 'tasks']
    else:
        st.session_state['sidebar_order'] = ['tasks', 'guide']


if st.sidebar.button("Re-Order Sidebar Order", on_click=toggle_sidebar_order):
    pass 


for section in st.session_state['sidebar_order']:
    if section == 'tasks':
        if all_tasks: 
            render_task_dashboard()
        else:
            st.sidebar.info("No tasks yet. Process emails first!")
    elif section == 'guide':
        render_quick_start_guide()

# Add a button to clear chat history (placed at the end)
if st.sidebar.button("🗑️ Clear Chat History"):
    st.session_state['chat_history'] = []
    st.rerun()