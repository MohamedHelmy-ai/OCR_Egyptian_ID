import os
import tempfile
from PIL import Image
import streamlit as st
import pandas as pd
import io
from utils import detect_and_process_id_card

# Streamlit configuration
st.set_page_config(page_title='Egyptian ID OCR', page_icon='💳', layout='wide')

# --- PERSISTENCE LOGIC ---
DB_FILE = "database.xlsx"

def load_data():
    if os.path.exists(DB_FILE):
        try:
            return pd.read_excel(DB_FILE)
        except Exception:
            return pd.DataFrame(columns=['First Name', 'Second Name', 'Full Name', 'National ID', 'Address', 'Birth Date', 'Governorate', 'Gender'])
    return pd.DataFrame(columns=['First Name', 'Second Name', 'Full Name', 'National ID', 'Address', 'Birth Date', 'Governorate', 'Gender'])

def save_data(df):
    df.to_excel(DB_FILE, index=False)

# Initialize session state
if 'id_database' not in st.session_state:
    st.session_state.id_database = load_data()

if "current_tab" not in st.session_state:
    st.session_state.current_tab = "Home"

if 'captured_image' not in st.session_state:
    st.session_state.captured_image = None

if 'is_confirmed' not in st.session_state:
    st.session_state.is_confirmed = False

# Sidebar navigation menu
tabs = ["Home", "Guide"]
st.sidebar.title("Navigation")
st.session_state.current_tab = st.sidebar.radio("Go to", tabs, index=tabs.index(st.session_state.current_tab))

if st.session_state.current_tab == "Home":
    st.title("💳 Egyptian ID Card OCR")
    
    # Sidebar options
    st.sidebar.subheader("Settings")
    input_method = st.sidebar.radio("Input Method", ["Camera Capture", "File Upload"])
    
    if st.sidebar.button("🔄 Reset / New Scan"):
        st.session_state.captured_image = None
        st.session_state.is_confirmed = False
        st.rerun()

    final_image_file = None

    if input_method == "File Upload":
        uploaded_file = st.file_uploader("Upload ID card image", type=['webp', 'jpg', 'jpeg', 'png', 'bmp'])
        if uploaded_file:
            final_image_file = uploaded_file
            st.session_state.is_confirmed = True # Auto-confirm for uploads
    else:
        # Camera Flow
        if not st.session_state.is_confirmed:
            st.info("💡 Tip: Use your phone's back camera for better results.")
            cam_image = st.camera_input("Take a photo of the ID card")
            
            if cam_image:
                st.session_state.captured_image = cam_image
                st.image(cam_image, caption="Review your photo", use_container_width=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Confirm & Scan", use_container_width=True):
                        st.session_state.is_confirmed = True
                        st.rerun()
                with col2:
                    if st.button("🔄 Retake Photo", use_container_width=True):
                        st.session_state.captured_image = None
                        st.session_state.is_confirmed = False
                        st.rerun()
        else:
            final_image_file = st.session_state.captured_image

    # Processing and Results
    if final_image_file and st.session_state.is_confirmed:
        with st.spinner("🔍 Scanning ID Card..."):
            try:
                # Save to temporary file for processing
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                    tmp.write(final_image_file.getvalue())
                    tmp_path = tmp.name

                # Perform OCR
                results_data = detect_and_process_id_card(tmp_path)
                
                # Unpack results
                f_name, s_name, full_name, n_id, addr, bday, gov, gen = results_data

                # Basic validation: if everything is empty, the detection likely failed
                if not any([f_name, s_name, n_id, addr]) or n_id == "":
                    st.warning("⚠️ Could not detect ID card details clearly. Please try again with better lighting or a closer shot.")
                    if st.button("Try Again"):
                        st.session_state.captured_image = None
                        st.session_state.is_confirmed = False
                        st.rerun()
                else:
                    results_dict = {
                        'First Name': f_name,
                        'Second Name': s_name,
                        'Full Name': full_name,
                        'National ID': n_id,
                        'Address': addr,
                        'Birth Date': bday,
                        'Governorate': gov,
                        'Gender': gen
                    }

                    # Display Processed Image (if available from utils)
                    if os.path.exists("d2.jpg"):
                        st.image("d2.jpg", caption="Detection Results", use_container_width=True)

                    st.success("✅ Extraction Complete!")
                    
                    # Show results in a structured way
                    st.subheader("📝 Extracted Information")
                    for key, val in results_dict.items():
                        st.write(f"**{key}:** {val}")

                    # Save Button
                    if st.button("💾 Save to Excel Database", use_container_width=True):
                        # Duplicate check
                        db = st.session_state.id_database
                        if str(n_id) in db['National ID'].astype(str).values:
                            st.warning(f"⚠️ ID {n_id} already exists in the database.")
                        else:
                            new_row = pd.DataFrame([results_dict])
                            st.session_state.id_database = pd.concat([db, new_row], ignore_index=True)
                            save_data(st.session_state.id_database)
                            st.success("🎉 Data saved successfully!")

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                st.info("This error usually happens if the ID card is not detected. Please try to take a clearer photo.")
                if st.button("Retry"):
                    st.session_state.captured_image = None
                    st.session_state.is_confirmed = False
                    st.rerun()
            finally:
                if 'tmp_path' in locals() and os.path.exists(tmp_path):
                    os.remove(tmp_path)

    elif not final_image_file and not st.session_state.is_confirmed:
        # Welcome screen / Placeholder
        if os.path.exists("ocr2.png"):
            st.image("ocr2.png", use_container_width=True)
        else:
            st.info("Welcome! Please capture a photo or upload an image to start scanning.")

    # Show Database
    if not st.session_state.id_database.empty:
        st.markdown("---")
        st.subheader("📋 Saved Records")
        st.dataframe(st.session_state.id_database, use_container_width=True)
        
        # Download
        buffer = io.BytesIO()
        st.session_state.id_database.to_excel(buffer, index=False)
        st.download_button(
            label="📥 Download Excel Report",
            data=buffer.getvalue(),
            file_name="id_records.xlsx",
            mime="application/vnd.ms-excel"
        )

elif st.session_state.current_tab == "Guide":
    st.title("📖 User Guide")
    st.markdown("""
    ### Steps to use:
    1. **Choose Input**: Use 'Camera Capture' for real-time scanning or 'File Upload' for saved images.
    2. **Take Photo**: Align the ID card in the frame. On mobile, use the **back camera** for best quality.
    3. **Preview**: After taking a photo, you can see it on screen.
    4. **Confirm/Retake**: If the photo is clear, click **Confirm & Scan**. If not, click **Retake**.
    5. **Review & Save**: Check the extracted text and click **Save to Excel Database**.
    
    ### Tips for Best Results:
    * **Lighting**: Avoid direct sunlight or strong glare on the card.
    * **Stability**: Hold the phone steady while capturing.
    * **Alignment**: Keep the card straight and centered.
    """)
