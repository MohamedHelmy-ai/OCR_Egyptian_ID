import os
import tempfile
from PIL import Image
import streamlit as st
import pandas as pd
import io
from utils import detect_and_process_id_card

# Streamlit configuration
st.set_page_config(page_title='ID Egyptian Card ', page_icon='💳', layout='wide')

# --- 1. Setup the Database (Session State keeps it active for multiple scans) ---
if 'id_database' not in st.session_state:
    st.session_state.id_database = pd.DataFrame(columns=[
        'First Name', 'Second Name', 'Full Name', 
        'National ID', 'Address', 'Birth Date', 
        'Governorate', 'Gender'
    ])

# Initialize session state for navigation
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "Home"

# Sidebar navigation menu
tabs = ["Home", "Guide"]
selected_tab = st.sidebar.radio("Navigation", tabs)

# Update the session state with the selected tab
st.session_state.current_tab = selected_tab

# Home Tab
if st.session_state.current_tab == "Home":
    uploaded_file = st.sidebar.file_uploader("Upload an ID card image",
                                             type=['webp', 'jpg', 'tif', 'tiff', 'png', 'mpo', 'bmp', 'jpeg', 'dng', 'pfm'])

    # If no file is uploaded, display the HOME image
    if not uploaded_file:
        st.image("ocr2.png", use_container_width=True)
    else:
        # If a file is uploaded, process it
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(uploaded_file.read())
            temp_file_path = temp_file.name

        image = Image.open(temp_file_path)

        st.subheader('Egyptian ID Card EXTRACTING, OCR 💳')
        st.sidebar.image(image)

        try:
            # Call the detect_and_process_id_card function
            first_name, second_name, Full_name, national_id, address, birth, gov, gender = detect_and_process_id_card(temp_file_path)
            
            # Create a results dictionary for the Excel logic
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

            st.image(Image.open("d2.jpg"), use_container_width=True)
            st.markdown("---")
            st.markdown(" ## WORDS EXTRACTED : ")
            
            # Display the dynamic results on screen
            for key, value in results.items():
                st.write(f"**{key}:** {value}")

            # --- 2. THE SAVE BUTTON ---
            if st.button("💾 Save this ID to Excel"):
                # Check for duplicates based on the National ID
                if str(results['National ID']) in st.session_state.id_database['National ID'].astype(str).values:
                    st.error(f"❌ Duplicate Found! ID {results['National ID']} is already in the Excel sheet.")
                else:
                    # Add to the list
                    new_entry = pd.DataFrame([results])
                    st.session_state.id_database = pd.concat([st.session_state.id_database, new_entry], ignore_index=True)
                    st.success(f"✅ ID {results['National ID']} added to the list!")

        except Exception as e:
            st.error(f"An error occurred: {e}")
        finally:
            os.remove(temp_file_path)

    # --- 3. DOWNLOAD SECTION (Visible on Home Tab) ---
    st.divider()
    st.subheader("📋 Scanned IDs List")
    st.dataframe(st.session_state.id_database)
    
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

# Documentation Tab
elif st.session_state.current_tab == "Guide":
    st.title("How to use our application 📖")
    st.write("""
    ## Project Overview:
    This application processes Egyptian ID cards to extract key information, including names, addresses, and national IDs.  
    It also decodes the national ID to provide additional details like birth date, governorate, and gender.

    ## Features:
    - **ID Card Detection**: Automatically detects and crops the ID card from the image.
    - **Field Detection**: Identifies key fields such as first name, last name, address, and serial number.
    - **Text Extraction**: Extracts Arabic and English text using EasyOCR.
    - **National ID Decoding**: Decodes the ID to extract:
        - Birth Date
        - Governorate
        - Gender
        - Birthplace
        - Location
        - Nationality

    ## How It Works:
    1. **Upload an Image**: Upload an image of the ID card using the sidebar.
    2. **Detection and Extraction**:
        - YOLO models detect the ID card and its fields.
        - EasyOCR extracts text from the identified fields.
    3. **Result Presentation**:
        - Outputs extracted information such as full name, address, and national ID details.
    4. **ID Decoding**:
        - Decodes the national ID to reveal demographic details.

    ## Steps to Use:
    - Get your image ready.
    - Click on Home.
    - Upload an Egyptian ID card image.
    - View the extracted information and analysis.
        
    ## هI HOPE YOU ENJOY THE EXPERIENCE 💖
    """)
