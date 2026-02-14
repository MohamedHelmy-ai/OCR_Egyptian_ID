import os
import tempfile
from PIL import Image
import streamlit as st
import pandas as pd
import io
from utils import detect_and_process_id_card

# Streamlit configuration
st.set_page_config(page_title='Egyptian ID Card Scanner', page_icon='💳', layout='wide')

# --- PERSISTENCE LOGIC ---
DB_FILE = "database.xlsx"

def load_data():
    """Loads the Excel database or creates an empty DataFrame."""
    if os.path.exists(DB_FILE):
        try:
            return pd.read_excel(DB_FILE)
        except Exception:
            return pd.DataFrame(columns=['First Name', 'Second Name', 'Full Name', 'National ID', 'Address', 'Birth Date', 'Governorate', 'Gender'])
    return pd.DataFrame(columns=['First Name', 'Second Name', 'Full Name', 'National ID', 'Address', 'Birth Date', 'Governorate', 'Gender'])

def save_data(df):
    """Saves the DataFrame to the Excel database."""
    df.to_excel(DB_FILE, index=False)

# --- IMAGE PROCESSING LOGIC ---
def process_image_data(image_bytes):
    """
    Processes image bytes, runs OCR, and displays results.
    This function now contains the core logic to avoid code duplication.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_file.write(image_bytes)
        temp_file_path = temp_file.name

    try:
        image = Image.open(temp_file_path)
        st.subheader('Egyptian ID Card EXTRACTING, OCR 💳')
        st.sidebar.image(image, caption="Scanned Image")

        # Call the main detection and processing function
        first_name, second_name, Full_name, national_id, address, birth, gov, gender = detect_and_process_id_card(temp_file_path)
        
        # --- FIX: Check if OCR returned valid data ---
        # If national_id is empty or None, it implies OCR failed.
        if not national_id:
            st.error("Could not extract a National ID. This might be due to a blurry image or poor lighting. Please try taking a clearer picture.")
            return # Stop further execution

        results = {
            'First Name': first_name,
            'Second Name': second_name,
            'Full Name': Full_name,
            'National ID': national_id,
            'Address': address,
            'Birth Date': birth,
            'Governorate': gov,
            'Gender': gender
        }

        if os.path.exists("d2.jpg"):
            st.image(Image.open("d2.jpg"), use_container_width=True)
        
        st.markdown("---")
        st.markdown(" ## WORDS EXTRACTED : ")
        
        for key, value in results.items():
            st.write(f"**{key}:** {value}")

        if st.button("💾 Save this ID to Excel"):
            if str(results['National ID']) in st.session_state.id_database['National ID'].astype(str).values:
                st.error(f"❌ Duplicate Found! ID {results['National ID']} is already in the list.")
            else:
                new_entry = pd.DataFrame([results])
                st.session_state.id_database = pd.concat([st.session_state.id_database, new_entry], ignore_index=True)
                save_data(st.session_state.id_database)
                st.success(f"✅ ID {results['National ID']} saved permanently!")

    # --- FIX: Specific error handling for "string index out of range" ---
    except IndexError:
        st.error("An error occurred: String index out of range. This usually happens when the OCR fails to read the ID card's text correctly. Please use a clearer, well-lit image and try again.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
    finally:
        # Clean up the temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


# --- MAIN APP LAYOUT ---

# Initialize database in session state
if 'id_database' not in st.session_state:
    st.session_state.id_database = load_data()

# Sidebar navigation
st.sidebar.title("Navigation")
selected_tab = st.sidebar.radio("Go to", ["Home", "Guide"])

# --- HOME TAB ---
if selected_tab == "Home":
    st.sidebar.divider()
    st.sidebar.header("Scan an ID")

    # --- NEW: Add Camera Input ---
    camera_photo = st.sidebar.camera_input(
        "📷 Take a picture of the ID",
        help="Click here to use your device's camera."
    )

    # --- MODIFIED: File Uploader ---
    uploaded_file = st.sidebar.file_uploader(
        "📂 Or upload an image",
        type=['webp', 'jpg', 'tif', 'tiff', 'png', 'mpo', 'bmp', 'jpeg', 'dng', 'pfm']
    )
    
    image_source = None
    if camera_photo:
        image_source = camera_photo
    elif uploaded_file:
        image_source = uploaded_file

    if image_source is None:
        st.title("Egyptian ID Card Scanner")
        if os.path.exists("ocr2.png"):
            st.image("ocr2.png", use_container_width=True)
        else:
            st.info("Welcome! Use the sidebar to take a photo or upload an ID card image to begin.")
    else:
        # Process the selected image (from camera or upload)
        process_image_data(image_source.read())

    # --- DOWNLOAD & VIEW SECTION ---
    st.divider()
    st.subheader("📋 Scanned IDs List (Persistent)")
    
    if not st.session_state.id_database.empty:
        if st.sidebar.button("🗑️ Clear All Data"):
            st.session_state.id_database = pd.DataFrame(columns=['First Name', 'Second Name', 'Full Name', 'National ID', 'Address', 'Birth Date', 'Governorate', 'Gender'])
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
            st.success("All data has been cleared.")
            st.rerun()

    st.dataframe(st.session_state.id_database, use_container_width=True)
    
    if not st.session_state.id_database.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            st.session_state.id_database.to_excel(writer, index=False)
        
        st.download_button(
            label="📥 Download All Results as Excel",
            data=buffer.getvalue(),
            file_name="scanned_ids.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# --- GUIDE TAB ---
elif selected_tab == "Guide":
    st.title("How to use our application 📖")
    st.write("""
    ## Project Overview:
    This application processes Egyptian ID cards to extract key information, including names, addresses, and national IDs.  
    It also decodes the national ID to provide additional details like birth date, governorate, and gender.

    ## How It Works:
    1. **Provide an Image**: Use the sidebar to either take a photo with your camera or upload an image file of the ID card.
    2. **Detection and Extraction**:
        - The app automatically detects and crops the ID card from the image.
        - It identifies key fields (name, address, etc.).
        - Advanced OCR extracts the Arabic text from these fields.
    3. **Result Presentation**:
        - The extracted information is displayed on the screen.
    4. **Save and Download**:
        - You can save the extracted data to a persistent list.
        - This list can be downloaded as an Excel file at any time.
        
    ### I HOPE YOU ENJOY THE EXPERIENCE 💖
    """)
