import urllib.parse
import streamlit as st
from supabase import Client, create_client

st.set_page_config(
    page_title="MyLinks - Cloud Hub",
    layout="centered",  # Centered layout looks much better on mobile and desktop
    initial_sidebar_state="collapsed",
)


@st.cache_resource
def init_supabase():
  return create_client(st.secrets["supabase"]["url"], st.secrets["supabase"]["key"])


supabase: Client = init_supabase()

if "user" not in st.session_state:
  st.session_state.user = None

# --- OTP AUTHENTICATION GATE ---
if not st.session_state.user:
  st.title("🔐 MyLinks - Secure Login")
  st.markdown(
      "Enter your email to sign in or automatically create an account via OTP."
  )

  if "otp_sent" not in st.session_state:
    st.session_state.otp_sent = False

  if not st.session_state.otp_sent:
    with st.form("request_otp_form"):
      email = st.text_input("Email Address")
      if st.form_submit_button("Send Login Code"):
        if email:
          try:
            supabase.auth.sign_in_with_otp({"email": email})
            st.session_state.pending_email = email
            st.session_state.otp_sent = True
            st.success("Check your email for the 6-digit login code!")
            st.rerun()
          except Exception as e:
            st.error(f"Failed to send code: {e}")
        else:
          st.error("Please enter an email address.")
  else:
    st.info(f"Verification code sent to: **{st.session_state.pending_email}**")
    with st.form("verify_otp_form"):
      token = st.text_input("Enter 6-Digit Code")
      col1, col2 = st.columns(2)
      with col1:
        if st.form_submit_button("Verify & Log In", type="primary"):
          try:
            res = supabase.auth.verify_otp({
                "email": st.session_state.pending_email,
                "token": token,
                "type": "email",
            })
            if res.user:
              st.session_state.user = res.user
              del st.session_state.otp_sent
              del st.session_state.pending_email
              st.rerun()
          except Exception as e:
            st.error(
                f"Invalid or expired code. Please try again. Details: {e}"
            )
      with col2:
        if st.form_submit_button("Use Different Email"):
          st.session_state.otp_sent = False
          st.rerun()

else:
  user = st.session_state.user
  user_uuid = user.id

  # --- TOP HEADER & LOGOUT ---
  head_col1, head_col2 = st.columns([3, 1])
  with head_col1:
    st.title("🌐 MyLinks Hub")
  with head_col2:
    if st.button("🚪 Log Out"):
      supabase.auth.sign_out()
      st.session_state.user = None
      st.rerun()

  st.divider()

  # --- INPUT RESOLUTION HELPER ---
  def resolve_input(user_input: str) -> str:
    cleaned = user_input.strip()
    if cleaned.lower().startswith(
        ("http://", "https://", "mailto:", "tel:", "spotify:", "zoommtg:")
    ):
      return cleaned
    if "." in cleaned and " " not in cleaned:
      return f"https://{cleaned}"
    encoded_query = urllib.parse.quote(cleaned)
    return f"https://www.google.com/search?q={encoded_query}"

  # Fetch Data from Supabase
  try:
    response = (
        supabase.table("shortcuts")
        .select("*")
        .eq("user_id", user_uuid)
        .order("created_at")
        .execute()
    )
    rows = response.data
  except Exception as e:
    st.error(f"Failed to load links: {e}")
    rows = []

  # Group by Category
  user_shortcuts = {}
  for row in rows:
    cat = row["category"]
    if cat not in user_shortcuts:
      user_shortcuts[cat] = []
    user_shortcuts[cat].append({
        "id": row["id"],
        "name": row["name"],
        "url_or_keyword": row["url_or_keyword"],
        "category": cat,
    })

  all_categories = list(user_shortcuts.keys())

  # --- MAIN CONTROLS (FILTER & ADD EXPANDER) ---
  control_col1, control_col2 = st.columns([2, 2])

  with control_col1:
    selected_category = st.selectbox(
        "📁 Filter Category", options=["All Categories"] + all_categories
    )

  with control_col2:
    st.write("")  # alignment spacing
    # Using an expander for adding new items keeps the main interface clean
    with st.expander("➕ Add New Item"):
      with st.form("add_mylink_form", clear_on_submit=True):
        cat_selection = st.selectbox(
            "Category", options=all_categories + ["+ New Category"]
        )

        category = cat_selection
        if cat_selection == "+ New Category":
          category = st.text_input("New Category Name")

        name = st.text_input("Display Name")
        input_val = st.text_input("URL or Keyword Phrase")

        if st.form_submit_button("Save Item", type="primary"):
          if name and input_val and category:
            try:
              supabase.table("shortcuts").insert({
                  "user_id": user_uuid,
                  "category": category,
                  "name": name,
                  "url_or_keyword": input_val,
              }).execute()
              st.success(f"Added {name}!")
              st.rerun()
            except Exception as e:
              st.error(f"Error saving: {e}")
          else:
            st.error("Please fill all fields.")

  st.write("")

  # --- MAIN DASHBOARD (TREE VIEW / COMPACT ONE-LINE ROWS) ---
  if not user_shortcuts:
    st.info("Your MyLinks dashboard is empty! Use 'Add New Item' above to start.")
  else:
    categories_to_show = (
        all_categories
        if selected_category == "All Categories"
        else [selected_category]
    )

    for category in categories_to_show:
      if category not in user_shortcuts:
        continue

      st.markdown(f"### 📂 {category}")
      links = user_shortcuts[category]

      for link in links:
        resolved_target = resolve_input(link["url_or_keyword"])

        # Compact mobile-friendly row layout
        cols = st.columns([5.5, 1, 1])

        with cols[0]:
          st.markdown(
              f"&nbsp;&nbsp;&nbsp;&nbsp;└── 🔗 [{link['name']}]({resolved_target})"
              f" <small style='color: gray;'>({link['url_or_keyword']})</small>",
              unsafe_allow_html=True,
          )

        with cols[1]:
          if st.button("✏️", key=f"edit_btn_{link['id']}", help="Edit item"):
            st.session_state[f"editing_{link['id']}"] = True

        with cols[2]:
          if st.button("🗑️", key=f"del_btn_{link['id']}", help="Delete item"):
            try:
              supabase.table("shortcuts").delete().eq(
                  "id", link["id"]
              ).execute()
              st.rerun()
            except Exception as e:
              st.error(f"Delete failed: {e}")

        # Inline Edit Form Expansion
        if st.session_state.get(f"editing_{link['id']}", False):
          with st.form(key=f"edit_form_{link['id']}"):
            st.write(f"**Edit: {link['name']}**")
            up_name = st.text_input(
                "Name", value=link["name"], key=f"up_name_{link['id']}"
            )
            up_val = st.text_input(
                "URL / Keyword",
                value=link["url_or_keyword"],
                key=f"up_val_{link['id']}",
            )
            up_cat = st.text_input(
                "Category", value=link["category"], key=f"up_cat_{link['id']}"
            )

            sub_col1, sub_col2 = st.columns(2)
            with sub_col1:
              if st.form_submit_button("Update"):
                try:
                  supabase.table("shortcuts").update({
                      "name": up_name,
                      "url_or_keyword": up_val,
                      "category": up_cat,
                  }).eq("id", link["id"]).execute()
                  st.session_state[f"editing_{link['id']}"] = False
                  st.rerun()
                except Exception as e:
                  st.error(f"Update failed: {e}")
            with sub_col2:
              if st.form_submit_button("Cancel"):
                st.session_state[f"editing_{link['id']}"] = False
                st.rerun()

      st.write("")