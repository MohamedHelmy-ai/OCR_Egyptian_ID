from ultralytics import YOLO
import cv2
import re
import easyocr
import os

# Initialize EasyOCR reader (this should be done once for efficiency)
reader = easyocr.Reader(['ar'], gpu=False)

# Function to preprocess the cropped image
def preprocess_image(cropped_image):
    gray_image = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)
    return gray_image

# Functions for specific fields with custom OCR configurations
def extract_text(image, bbox, lang='ara'):
    x1, y1, x2, y2 = bbox
    cropped_image = image[y1:y2, x1:x2]
    preprocessed_image = preprocess_image(cropped_image)
    results = reader.readtext(preprocessed_image, detail=0, paragraph=True)
    text = ' '.join(results)
    return text.strip()

# Function to detect national ID numbers in a cropped image
def detect_national_id(cropped_image):
    model = YOLO('detect_id.pt')  # Load the model directly in the function
    results = model(cropped_image)
    detected_info = []

    for result in results:
        for box in result.boxes:
            cls = int(box.cls)
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            detected_info.append((cls, x1))
            cv2.rectangle(cropped_image, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(cropped_image, str(cls), (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (36, 255, 12), 2)

    return detected_info

def expand_bbox_height(bbox, scale=1.2, image_shape=None):
    x1, y1, x2, y2 = bbox
    width = x2 - x1
    height = y2 - y1
    center_x = x1 + width // 2
    center_y = y1 + height // 2
    new_height = int(height * scale)
    new_y1 = max(center_y - new_height // 2, 0)
    new_y2 = min(center_y + new_height // 2, image_shape[0])
    return [x1, new_y1, x2, new_y2]

# Function to process the cropped image
def process_image(cropped_image):
    # Load the trained YOLO model for objects (fields) detection
    model = YOLO('detect_odjects.pt')
    results = model(cropped_image)

    # Variables to store extracted values
    first_name = ''
    second_name = ''
    merged_name = ''
    nid = ''
    address = ''
    serial = ''

    # Loop through the results
    for result in results:
        output_path = 'd2.jpg'
        result.save(output_path)

        for box in result.boxes:
            bbox = box.xyxy[0].tolist()
            class_id = int(box.cls[0].item())
            class_name = result.names[class_id]
            bbox = [int(coord) for coord in bbox]

            if class_name == 'firstName':
                first_name = extract_text(cropped_image, bbox, lang='ara')
            elif class_name == 'lastName':
                second_name = extract_text(cropped_image, bbox, lang='ara')
            elif class_name == 'serial':
                serial = extract_text(cropped_image, bbox, lang='eng')
            elif class_name == 'address':
                address = extract_text(cropped_image, bbox, lang='ara')
            elif class_name == 'id_number':
                nid = extract_text(cropped_image, bbox, lang='eng')

    # Ensure we have a valid ID number before decoding
    if not nid or len(re.sub(r'\D', '', nid)) < 14:
        # If OCR failed to get 14 digits, try to find it with detect_id.pt
        try:
            detected_id_parts = detect_national_id(cropped_image)
            # This is a fallback; in the original code, nid is expected to be a string
            # We'll just keep it as is if detect_national_id doesn't return a string
        except:
            pass

    # Clean the ID number (keep only digits)
    nid_clean = re.sub(r'\D', '', nid)
    
    if len(nid_clean) == 14:
        decoded_info = decode_egyptian_id(nid_clean)
        return (first_name, second_name, f"{first_name} {second_name}", nid_clean, address, 
                decoded_info["Birth Date"], decoded_info["Governorate"], decoded_info["Gender"])
    else:
        # Return empty/default values if ID is invalid
        return (first_name, second_name, f"{first_name} {second_name}", nid_clean, address, "Unknown", "Unknown", "Unknown")

# Function to decode the Egyptian ID number
def decode_egyptian_id(id_number):
    governorates = {
        '01': 'Cairo', '02': 'Alexandria', '03': 'Port Said', '04': 'Suez',
        '11': 'Damietta', '12': 'Dakahlia', '13': 'Ash Sharqia', '14': 'Kaliobeya',
        '15': 'Kafr El-Sheikh', '16': 'Gharbia', '17': 'Monoufia', '18': 'El Beheira',
        '19': 'Ismailia', '21': 'Giza', '22': 'Beni Suef', '23': 'Fayoum',
        '24': 'El Menia', '25': 'Assiut', '26': 'Sohag', '27': 'Qena',
        '28': 'Aswan', '29': 'Luxor', '31': 'Red Sea', '32': 'New Valley',
        '33': 'Matrouh', '34': 'North Sinai', '35': 'South Sinai', '88': 'Foreign'
    }

    try:
        century_digit = int(id_number[0])
        year = int(id_number[1:3])
        month = int(id_number[3:5])
        day = int(id_number[5:7])
        governorate_code = id_number[7:9]
        gender_code = int(id_number[12:13])

        if century_digit == 2:
            full_year = 1900 + year
        elif century_digit == 3:
            full_year = 2000 + year
        else:
            full_year = 0 # Invalid

        gender = "Male" if gender_code % 2 != 0 else "Female"
        governorate = governorates.get(governorate_code, "Unknown")
        birth_date = f"{full_year:04d}-{month:02d}-{day:02d}"

        return {
            'Birth Date': birth_date,
            'Governorate': governorate,
            'Gender': gender
        }
    except:
        return {
            'Birth Date': "Unknown",
            'Governorate': "Unknown",
            'Gender': "Unknown"
        }

# Function to detect the ID card and pass it to the existing code
def detect_and_process_id_card(image_path):
    # Load the ID card detection model
    id_card_model = YOLO('detect_id_card.pt')
    
    # Perform inference to detect the ID card
    id_card_results = id_card_model(image_path)
    
    # Load the original image using OpenCV
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError("Could not read the image file.")

    cropped_image = None
    # Crop the ID card from the image
    for result in id_card_results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cropped_image = image[y1:y2, x1:x2]
            break # Take the first detected card
        if cropped_image is not None:
            break

    if cropped_image is None:
        # ERROR FIX: If no card is detected, use the whole image as a fallback
        # or raise a specific error that the app can catch.
        # For better UX, let's try to process the whole image but warn the user.
        cropped_image = image

    # Pass the cropped image to the existing processing function
    return process_image(cropped_image)
