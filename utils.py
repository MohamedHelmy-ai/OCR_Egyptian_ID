from ultralytics import YOLO
import cv2
import re
import easyocr
from PIL import Image

# --- OPTIMIZATION: Load models and reader only once ---
# This prevents reloading them on every single image, which is slow.
try:
    reader = easyocr.Reader(['ar'], gpu=False)
    id_card_detector = YOLO('detect_id_card.pt')
    field_detector = YOLO('detect_odjects.pt')
    nid_digit_detector = YOLO('detect_id.pt')
    print("Models and OCR reader loaded successfully.")
except Exception as e:
    print(f"Error loading models or EasyOCR reader: {e}")
    # Handle the case where model files might be missing
    reader = id_card_detector = field_detector = nid_digit_detector = None

# --- Helper Functions (No major changes needed here) ---

def preprocess_image(cropped_image):
    """Converts a cropped image to grayscale."""
    return cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)

def extract_text(image, bbox):
    """Extracts text from a given bounding box using EasyOCR."""
    x1, y1, x2, y2 = bbox
    cropped_image = image[y1:y2, x1:x2]
    preprocessed_image = preprocess_image(cropped_image)
    results = reader.readtext(preprocessed_image, detail=0, paragraph=True)
    return ' '.join(results).strip()

def expand_bbox_height(bbox, scale=1.5, image_shape=None):
    """Expands the height of a bounding box to better capture text."""
    x1, y1, x2, y2 = bbox
    height = y2 - y1
    center_y = y1 + height // 2
    new_height = int(height * scale)
    new_y1 = max(center_y - new_height // 2, 0)
    new_y2 = min(center_y + new_height // 2, image_shape[0])
    return [x1, new_y1, x2, new_y2]

def detect_national_id_digits(cropped_nid_image):
    """Detects individual digits to form the National ID number."""
    if nid_digit_detector is None: return ""
    results = nid_digit_detector(cropped_nid_image)
    detected_info = []
    for result in results:
        for box in result.boxes:
            cls = int(box.cls)
            x1, _, _, _ = map(int, box.xyxy[0])
            detected_info.append((cls, x1))
    
    detected_info.sort(key=lambda x: x[1])
    return ''.join([str(cls) for cls, _ in detected_info])

def decode_egyptian_id(id_number):
    """Decodes a 14-digit Egyptian ID number into structured data."""
    if not id_number or len(id_number) != 14:
        return {'Birth Date': '', 'Governorate': '', 'Gender': ''}
    
    governorates = {
        '01': 'Cairo', '02': 'Alexandria', '03': 'Port Said', '04': 'Suez',
        '11': 'Damietta', '12': 'Dakahlia', '13': 'Ash Sharqia', '14': 'Kaliobeya',
        '15': 'Kafr El - Sheikh', '16': 'Gharbia', '17': 'Monoufia', '18': 'El Beheira',
        '19': 'Ismailia', '21': 'Giza', '22': 'Beni Suef', '23': 'Fayoum',
        '24': 'El Menia', '25': 'Assiut', '26': 'Sohag', '27': 'Qena',
        '28': 'Aswan', '29': 'Luxor', '31': 'Red Sea', '32': 'New Valley',
        '33': 'Matrouh', '34': 'North Sinai', '35': 'South Sinai', '88': 'Foreign'
    }
    try:
        century_digit, year, month, day = int(id_number[0]), int(id_number[1:3]), int(id_number[3:5]), int(id_number[5:7])
        governorate_code, gender_code = id_number[7:9], int(id_number[12])
        full_year = (1900 if century_digit == 2 else 2000) + year
        gender = "Male" if gender_code % 2 != 0 else "Female"
        governorate = governorates.get(governorate_code, "Unknown")
        birth_date = f"{full_year:04d}-{month:02d}-{day:02d}"
        return {'Birth Date': birth_date, 'Governorate': governorate, 'Gender': gender}
    except (ValueError, IndexError):
        return {'Birth Date': '', 'Governorate': '', 'Gender': ''}

# --- Main Processing Functions ---

def process_fields(cropped_image):
    """Processes the cropped ID card to extract all text fields."""
    if field_detector is None:
        return "", "", "", "", ""

    results = field_detector(cropped_image)
    first_name, second_name, address, nid = "", "", "", ""

    # Save detection visualization
    if results:
        # This is for debugging, you can comment it out later
        results[0].save(filename='d2.jpg') 

    for result in results:
        for box in result.boxes:
            bbox = [int(coord) for coord in box.xyxy[0].tolist()]
            class_name = result.names[int(box.cls[0].item())]

            if class_name == 'firstName':
                first_name = extract_text(cropped_image, bbox)
            elif class_name == 'lastName':
                second_name = extract_text(cropped_image, bbox)
            elif class_name == 'address':
                address = extract_text(cropped_image, bbox)
            elif class_name == 'nid':
                expanded_bbox = expand_bbox_height(bbox, image_shape=cropped_image.shape)
                cropped_nid_area = cropped_image[expanded_bbox[1]:expanded_bbox[3], expanded_bbox[0]:expanded_bbox[2]]
                nid = detect_national_id_digits(cropped_nid_area)
    
    full_name = f"{first_name} {second_name}".strip()
    return first_name, second_name, full_name, nid, address

def detect_and_process_id_card(image_path):
    """
    Main function called by app.py. Detects the ID card, crops it,
    and then processes the cropped image to extract information.
    Returns empty strings if any step fails.
    """
    # --- FIX: Initialize all return values to be empty ---
    first_name, second_name, full_name, nid, address, birth, gov, gender = "", "", "", "", "", "", "", ""

    if id_card_detector is None:
        print("ID Card detector model is not loaded.")
        return first_name, second_name, full_name, nid, address, birth, gov, gender

    try:
        image = cv2.imread(image_path)
        if image is None:
            print(f"Error: Could not read image from path: {image_path}")
            return first_name, second_name, full_name, nid, address, birth, gov, gender

        id_card_results = id_card_detector(image)
        
        # --- FIX: Initialize cropped_image to None ---
        cropped_image = None
        
        # --- FIX: Check if detection was successful before cropping ---
        if id_card_results and len(id_card_results[0].boxes) > 0:
            # Assume the largest detected box is the ID card
            best_box = max(id_card_results[0].boxes, key=lambda box: (box.xyxy[0][2] - box.xyxy[0][0]) * (box.xyxy[0][3] - box.xyxy[0][1]))
            x1, y1, x2, y2 = map(int, best_box.xyxy[0])
            cropped_image = image[y1:y2, x1:x2]
        else:
            print("ID card detection failed. No card found in the image.")

        # --- FIX: Only proceed if the ID card was successfully cropped ---
        if cropped_image is not None:
            first_name, second_name, full_name, nid, address = process_fields(cropped_image)
            decoded_info = decode_egyptian_id(nid)
            birth, gov, gender = decoded_info['Birth Date'], decoded_info['Governorate'], decoded_info['Gender']
        
    except Exception as e:
        print(f"An error occurred during card detection or processing: {e}")
        # The function will fall through and return the empty strings

    return first_name, second_name, full_name, nid, address, birth, gov, gender
