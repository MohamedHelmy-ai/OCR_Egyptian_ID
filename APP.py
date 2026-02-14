import os
import tempfile
from PIL import Image
import streamlit as st
import pandas as pd
import io
from utils import detect_and_process_id_card

# Import libraries for webrtc and image handling
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, WebRtcMode
import av
import cv2 # Using cv2 for color conversion
import threading

# Streamlit configuration
st.set_page_config(page_title='Egyptian ID Card Scanner', page_icon='💳', layout='wide')

# --- CSS for the Visual Guide Overlay ---
# We define a pseudo-element (::before) to draw the rectangle over the video.
# This is more robust than trying to overlay HTML elements.
st.markdown("""
    <style>
    .video-container {
        position: relative;
        width: 100%;
    }
    .video-container video {
        width: 100%;
        height: auto;
        border: 1px solid #ccc;
        border-radius: 5px;
    }
    .video-container::before {
        content: '';
        position: absolute;
        /* Center the rectangle */
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        
        /* ID Card aspect ratio is approx 85.6mm x 53.98mm ~= 1.586 */
        /* We'll use width and padding-top to maintain aspect ratio */
        width: 85%; /* Adjust width of the guide */
        padding-top: 53.5%; /* 85% / 1.586 (aspect ratio) */
        
        /* Style the guide */
        border: 3px dashed rgba(255, 255, 255, 0.7);
        border-radius: 10px;
        box-shadow: 0 0 15px rgba(0, 0, 0, 0.5);
        
        pointer-events: none; /* Allows clicking 'through' the overlay */
    }
    </style>
""", unsafe_allow_html=True)


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

# --- WEBRTC FRAME CAPTURING LOGIC ---
lock = threading.Lock()
img_container = {"img": None}

class VideoProcessor(VideoProcessorBase):
    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        with lock:
            img_container["img"] = img
        return frame

# --- IMAGE PROCESSING LOGIC ---
def process_image_data(image_bytes):
    # This function remains the same as before
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
        temp_file.write(image_bytes)
        temp_file_path = temp_file.name

    try:
        image = Image.open(temp_file_path)
        st.subheader('Egyptian ID Card EXTRACTING, OCR 💳')
        st.sidebar.image(image, caption="Captured Image")

        first_name, second_name, Full_name, national_id, address, birth, gov, gender = detect_and_process_id_card(temp_file_path)
        
        if not national_id:
            st.error("Could not extract a National ID. This might be due to a blurry image or poor lighting. Please try taking a clearer picture.")
            return

        results = {
            'First Name': first_name, 'Second Name': second_name, 'Full Name': Full_name,
            'National ID': national_id, 'Address': address, 'Birth Date': birth,
            'Governorate': gov, 'Gender': gender
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

    except IndexError:
        st.error("An error occurred: String index out of range. This usually happens when the OCR fails to read the ID card's text correctly. Please use a clearer, well-lit image and try again.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

# --- MAIN APP LAYOUT ---
if 'id_database' not in st.session_state:
    st.session_state.id_database = load_data()

st.sidebar.title("Navigation")
selected_tab = st.sidebar.radio("Go to", ["Home", "Guide"])

if selected_tab == "Home":
    st.sidebar.divider()
    st.sidebar.header("Scan an ID")
    st.sidebar.info("Align the ID card within the dashed rectangle and click 'Capture Photo'.")

    # --- MODIFIED: Added a container with the CSS class ---
    with st.sidebar.container():
        webrtc_ctx = webrtc_streamer(
            key="id-scanner",
            mode=WebRtcMode.SENDONLY,
            video_processor_factory=VideoProcessor,
            media_stream_constraints={
                "video": {"facingMode": "environment"},
                "audio": False,
            },
            # Assign the class to the container of the video element
            video_html_attrs={"class": "video-container"},
            async_processing=True,
        )

    if webrtc_ctx.state.playing:
        if st.sidebar.button("📸 Capture Photo"):
            with lock:
                img = img_container["img"]
            if img is not None:
                st.sidebar.success("Photo captured!")
                # Convert BGR (from OpenCV) to RGB (for PIL)
                rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(rgb_img)
                
                buf = io.BytesIO()
                pil_image.save(buf, format="JPEG")
                image_bytes = buf.getvalue()
                
                process_image_data(image_bytes)
            else:
                st.sidebar.warning("Camera is starting... please wait a moment and try again.")

    st.sidebar.divider()
    uploaded_file = st.sidebar.file_uploader(
        "📂 Or upload an image",
        type=['webp', 'jpg', 'png', 'jpeg']
    )

    if uploaded_file:
        process_image_data(uploaded_file.read())
    
    # Logic to show the main page content
    if 'main_content_placeholder' not in st.session_state:
        st.session_state.main_content_placeholder = st.empty()

    # This part is tricky with reruns. A simple approach:
    # We only show the welcome image if no image has been processed yet.
    # A better state management would be needed for complex scenarios.
    if not uploaded_file and not webrtc_ctx.state.playing:
        with st.session_state.main_content_placeholder.container():
            st.title("Egyptian ID Card Scanner")
            if os.path.exists("ocr2.png"):
                st.image("ocr2.png", use_container_width=True)
            else:
                st.info("Welcome! Use the sidebar to start your camera or upload an ID card image.")

    # --- DOWNLOAD & VIEW SECTION (in the main area) ---
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

elif selected_tab == "Guide":
    st.title("How to use our application 📖")
    # (Guide content remains the same)
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
