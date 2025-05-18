from flask import Flask, request, render_template, send_file, jsonify
from PIL import Image, ImageDraw, ImageEnhance
from werkzeug.utils import secure_filename
import os
import io
import base64

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB 제한
app.config['UPLOAD_FOLDER'] = 'uploads'

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def add_rounded_corners(image, radius):
    circle = Image.new('L', (radius * 2, radius * 2), 0)
    draw = ImageDraw.Draw(circle)
    draw.ellipse((0, 0, radius * 2 - 1, radius * 2 - 1), fill=255)
    
    output = Image.new('RGBA', image.size, (255, 255, 255, 0))
    output.paste(image, (0, 0))
    
    alpha = Image.new('L', image.size, 255)
    
    # 각 모서리에 원형 마스크 적용
    alpha.paste(circle.crop((0, 0, radius, radius)), (0, 0))  # 좌상단
    alpha.paste(circle.crop((radius, 0, radius * 2, radius)), (image.width - radius, 0))  # 우상단
    alpha.paste(circle.crop((0, radius, radius, radius * 2)), (0, image.height - radius))  # 좌하단
    alpha.paste(circle.crop((radius, radius, radius * 2, radius * 2)), (image.width - radius, image.height - radius))  # 우하단
    
    output.putalpha(alpha)
    return output

def image_to_base64(image):
    buffered = io.BytesIO()
    image.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def adjust_image(image, saturation, brightness):
    # 채도 조절
    enhancer = ImageEnhance.Color(image)
    image = enhancer.enhance(saturation)
    
    # 명도 조절
    enhancer = ImageEnhance.Brightness(image)
    image = enhancer.enhance(brightness)
    
    return image

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        # 이미지 처리
        image = Image.open(file)
        
        # 원본 이미지를 base64로 변환
        original_base64 = image_to_base64(image)
        
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        # 이미지 객체를 메모리에 저장
        img_io = io.BytesIO()
        image.save(img_io, 'PNG')
        img_io.seek(0)
        
        return jsonify({
            'original': original_base64,
            'image_data': base64.b64encode(img_io.getvalue()).decode(),
            'filename': secure_filename(file.filename)
        })
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/process', methods=['POST'])
def process_image():
    try:
        data = request.json
        image_data = base64.b64decode(data['image_data'])
        radius = int(data['radius'])
        saturation = float(data['saturation'])
        brightness = float(data['brightness'])
        
        # 이미지 처리
        image = Image.open(io.BytesIO(image_data))
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        # 채도와 명도 조절
        image = adjust_image(image, saturation, brightness)
        
        # 모서리 둥글게 처리
        rounded_image = add_rounded_corners(image, radius)
        
        # 변환된 이미지를 base64로 변환
        rounded_base64 = image_to_base64(rounded_image)
        
        return jsonify({
            'rounded': rounded_base64
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download', methods=['POST'])
def download_file():
    if 'image' not in request.json:
        return 'No image data', 400
    
    image_data = request.json['image'].split(',')[1]  # Remove data URL prefix
    filename = request.json.get('filename', 'rounded_image.png')
    
    # base64 디코딩
    image_binary = base64.b64decode(image_data)
    
    return send_file(
        io.BytesIO(image_binary),
        mimetype='image/png',
        as_attachment=True,
        download_name=filename
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port) 