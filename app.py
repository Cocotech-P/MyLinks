import urllib.parse
import streamlit as st
from supabase import Client, create_client

st.set_page_config(
    page_title="MyLinks - Cloud Hub",
    layout="centered",
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


  # --- INPUT RESOLUTION HELPER (Combines URL/App with Key Words) ---
  def resolve_input(url_or_app: str, keywords: str) -> str:
    base = url_or_app.strip()

    # Determine base target URL/App scheme
    if base.lower().startswith(
        ("http://", "https://", "mailto:", "tel:", "spotify:", "zoommtg:")
    ):
      target = base
    elif "." in base and " " not in base:
      target = f"https://{base}"
    else:
      encoded_query = urllib.parse.quote(base)
      target = f"https://www.google.com/search?q={encoded_query}"

    # If keywords are provided, combine them into the target URL search parameter
    if keywords and keywords.strip():
      kw_encoded = urllib.parse.quote(keywords.strip())
      # If the target already has query parameters or needs a search query append
      if "?" in target:
        target = f"{target}&q={kw_encoded}"
      else:
        target = f"{target}?q={kw_encoded}"

    return target


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
  all_cats_set = set()
  for row in rows:
    cat = row["category"] or "General"
    all_cats_set.add(cat)
    if cat not in user_shortcuts:
      user_shortcuts[cat] = []
    user_shortcuts[cat].append({
        "id": row["id"],
        "name": row["name"],
        "keywords": row.get("keywords", ""),
        "url_or_keyword": row["url_or_keyword"],
        "category": cat,
    })

  all_categories = sorted(list(all_cats_set))
  if not all_categories:
    all_categories = ["General"]

  # --- SIDEBAR (HAMBURGER MENU) FOR MANAGEMENT ---
  with st.sidebar:
    st.title("⚙️ Management")
    if st.button("🚪 Log Out", use_container_width=True):
      supabase.auth.sign_out()
      st.session_state.user = None
      st.rerun()

    st.divider()

    # 1. Add New Item
    st.subheader("➕ Add New Link")
    with st.form("sidebar_add_form", clear_on_submit=True):
      new_name = st.text_input("Link Name")
      new_kw = st.text_input("Optional: Key Words")
      new_url = st.text_input("Link URL or App")
      new_cat = st.selectbox(
          "Category", options=all_categories + ["+ Create New Category"]
      )
      custom_cat = ""
      if new_cat == "+ Create New Category":
        custom_cat = st.text_input("New Category Name")

      if st.form_submit_button("Save Item", type="primary"):
        target_cat = (
            custom_cat.strip()
            if new_cat == "+ Create New Category"
            else new_cat
        )
        if new_name and new_url and target_cat:
          try:
            supabase.table("shortcuts").insert({
                "user_id": user_uuid,
                "category": target_cat,
                "name": new_name,
                "keywords": new_kw,
                "url_or_keyword": new_url,
            }).execute()
            st.success("Added successfully!")
            st.rerun()
          except Exception as e:
            st.error(f"Error saving: {e}")
        else:
          st.error("Please fill required fields.")

    st.divider()

    # 2. Edit / Delete Existing Items
    st.subheader("✏️ Edit or Delete")
    if rows:
      link_options = {f"{r['name']} ({r['category']})": r for r in rows}
      selected_link_label = st.selectbox(
          "Select Link to Manage", options=list(link_options.keys())
      )
      selected_link = link_options[selected_link_label]

      with st.form("sidebar_edit_form"):
        up_name = st.text_input("Link Name", value=selected_link["name"])
        up_kw = st.text_input(
            "Optional: Key Words", value=selected_link.get("keywords", "")
        )
        up_url = st.text_input(
            "URL or App", value=selected_link["url_or_keyword"]
        )
        up_cat = st.text_input("Category", value=selected_link["category"])

        col_save, col_del = st.columns(2)
        with col_save:
          if st.form_submit_button("Save Changes"):
            try:
              supabase.table("shortcuts").update({
                  "name": up_name,
                  "keywords": up_kw,
                  "url_or_keyword": up_url,
                  "category": up_cat,
              }).eq("id", selected_link["id"]).execute()
              st.success("Updated!")
              st.rerun()
            except Exception as e:
              st.error(f"Update failed: {e}")
        with col_del:
          if st.form_submit_button("Delete Item"):
            try:
              supabase.table("shortcuts").delete().eq(
                  "id", selected_link["id"]
              ).execute()
              st.success("Deleted!")
              st.rerun()
            except Exception as e:
              st.error(f"Delete failed: {e}")
    else:
      st.info("No links available to edit.")

  # --- MAIN SCREEN ---
  st.title("🌐 MyLinks")

  # Category Tabs across the top
  selected_cat = st.tabs(all_categories)

  for idx, category in enumerate(all_categories):
    with selected_cat[idx]:
      st.write("")
      links = user_shortcuts.get(category, [])

      if not links:
        st.info(
            f"No links found in '{category}'. Use the sidebar menu (☰) to add"
            " items."
        )
      else:
        for link in links:
          resolved_target = resolve_input(
              link["url_or_keyword"], link.get("keywords", "")
          )

          # Display ONLY the Link Name as a clean single-line button item
          st.link_button(
              f"🔗 {link['name']}",
              url=resolved_target,
              use_container_width=True,
          )

      st.write("")
