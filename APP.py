import os
import tempfile
from PIL import Image
import streamlit as st
import pandas as pd
import io
import cv2
import threading
import av

# Import your custom utility functions
from utils import detect_and_process_id_card

# --- Page and Component Configuration ---
st.set_page_config(page_title='Egyptian ID Card Scanner', page_icon='💳', layout="wide")

# CSS for the visual guide overlay on the camera
st.markdown("""
    <style>
    .video-container { position: relative; width: 100%; }
    .video-container video { width: 100%; height: auto; border: 1px solid #ccc; border-radius: 10px; }
    .video-container::before {
        content: 'Align ID Card Here';
        position: absolute; top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        width: 85%; padding-top: 53.5%;
        border: 3px dashed rgba(255, 255, 255, 0.7);
        border-radius: 15px;
        box-shadow: 0 0 15px rgba(0, 0, 0, 0.5);
        pointer-events: none;
        color: rgba(255, 255, 255, 0.8);
        font-size: 1.5rem; font-weight: bold;
        display: flex; align-items: center; justify-content: center;
        text-shadow: 2px 2px 4px #000000;
    }
    </style>
""", unsafe_allow_html=True)

# --- Data Persistence Functions ---
DB_FILE = "database.xlsx"
def load_data():
    if os.path.exists(DB_FILE):
        try: return pd.read_excel(DB_FILE)
        except Exception: return pd.DataFrame(columns=['First Name', 'Second Name', 'Full Name', 'National ID', 'Address', 'Birth Date', 'Governorate', 'Gender'])
    return pd.DataFrame(columns=['First Name', 'Second Name', 'Full Name', 'National ID', 'Address', 'Birth Date', 'Governorate', 'Gender'])

def save_data(df):
    df.to_excel(DB_FILE, index=False)

# --- Real-Time Camera Processing Class ---
class VideoProcessor(VideoProcessorBase):
    def __init__(self):
        self.frame_lock = threading.Lock()
        self.latest_frame = None
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        with self.frame_lock:
            self.latest_frame = frame.to_ndarray(format="bgr24")
        return frame

# --- Core Image Processing and Display Function ---
def display_results(image_bytes):
    """Takes image bytes, runs processing, and displays results."""
    st.subheader('Extracted Information')
    with st.spinner('Detecting ID card and extracting text...'):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(image_bytes)
            temp_file_path = temp_file.name
        
        try:
            # Call your main processing function from utils.py
            first_name, second_name, full_name, nid, address, birth, gov, gender = detect_and_process_id_card(temp_file_path)
            
            if not nid:
                st.error("Could not extract a National ID. This might be due to a blurry image, poor lighting, or the ID not being detected. Please try again.")
                return

            results = {
                'First Name': first_name, 'Second Name': second_name, 'Full Name': full_name,
                'National ID': nid, 'Address': address, 'Birth Date': birth,
                'Governorate': gov, 'Gender': gender
            }
            
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
                    st.rerun() # Rerun to update the dataframe view

        except UnboundLocalError:
            st.error("Critical Error: Failed to detect the ID card in the image. Please ensure the entire card is visible and the picture is clear.")
        except Exception as e:
            st.error(f"An unexpected error occurred during processing: {e}")
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

# --- Main Application ---

# Initialize session state for database
if 'id_database' not in st.session_state:
    st.session_state.id_database = load_data()

# Sidebar for navigation and controls
st.sidebar.title("Navigation")
selected_tab = st.sidebar.radio("Go to", ["Home", "Guide"])

if selected_tab == "Home":
    st.title("Egyptian ID Card Scanner")
    
    # Sidebar controls for image input
    st.sidebar.divider()
    st.sidebar.header("Controls")
    input_method = st.sidebar.radio("Choose input method:", ("Camera", "Upload Image"))

    # --- Main Page Layout ---
    col1, col2 = st.columns([2, 3]) # Give more space to the results column

    # --- CAMERA MODE ---
    if input_method == "Camera":
        with col1:
            st.subheader("Camera View")
            webrtc_ctx = webrtc_streamer(
                key="id-scanner",
                mode=WebRtcMode.SENDONLY,
                video_processor_factory=VideoProcessor,
                media_stream_constraints={"video": {"facingMode": "environment"}, "audio": False},
                video_html_attrs={"class": "video-container"},
                async_processing=True,
            )
        
        if webrtc_ctx.state.playing and webrtc_ctx.video_processor:
            if st.sidebar.button("📸 Capture Photo"):
                with webrtc_ctx.video_processor.frame_lock:
                    captured_frame = webrtc_ctx.video_processor.latest_frame
                
                if captured_frame is not None:
                    st.sidebar.success("Photo captured!")
                    st.sidebar.image(captured_frame, channels="BGR", caption="Last Captured Image")
                    
                    # Convert to bytes and process
                    rgb_img = cv2.cvtColor(captured_frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(rgb_img)
                    buf = io.BytesIO()
                    pil_image.save(buf, format="JPEG")
                    image_bytes = buf.getvalue()
                    
                    with col2:
                        display_results(image_bytes)
                else:
                    st.sidebar.warning("Camera is not ready. Please wait a moment.")
        with col2:
            if 'webrtc_ctx' not in locals() or not webrtc_ctx.state.playing:
                 st.info("Start the camera from the main view to begin scanning.")

    # --- UPLOAD MODE ---
    elif input_method == "Upload Image":
        uploaded_file = st.sidebar.file_uploader("Drag and drop or browse files", type=['jpg', 'jpeg', 'png'])
        
        if uploaded_file is not None:
            with col1:
                st.subheader("Uploaded Image")
                st.image(uploaded_file, caption="Your uploaded ID card.")
            with col2:
                image_bytes = uploaded_file.getvalue()
                display_results(image_bytes)
        else:
            with col1:
                st.info("Please upload an image file using the control in the sidebar.")

    # --- Scanned IDs Database (always visible) ---
    st.divider()
    st.subheader("📋 Scanned IDs List (Persistent)")
    st.dataframe(st.session_state.id_database, use_container_width=True)
    
    if not st.session_state.id_database.empty:
        # Add clear and download buttons to the sidebar for better organization
        if st.sidebar.button("🗑️ Clear All Data"):
            st.session_state.id_database = pd.DataFrame(columns=['First Name', 'Second Name', 'Full Name', 'National ID', 'Address', 'Birth Date', 'Governorate', 'Gender'])
            if os.path.exists(DB_FILE): os.remove(DB_FILE)
            st.success("All data has been cleared.")
            st.rerun()
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            st.session_state.id_database.to_excel(writer, index=False)
        st.sidebar.download_button(
            label="📥 Download All Results as Excel",
            data=buffer.getvalue(),
            file_name="scanned_ids.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

elif selected_tab == "Guide":
    st.title("How to use our application 📖")
    st.write(""".## Project Overview:
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
    """)# Your guide content here
