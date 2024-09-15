import os
import fitz  # PyMuPDF
import pandas as pd
from flask import Flask, request, redirect, render_template, flash, jsonify
from sqlalchemy import create_engine
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DATABASE'] = 'sqlite:///pdf_data.db'
app.secret_key = 'supersecretkey'

engine = create_engine(app.config['DATABASE'])

# Função para verificar extensão permitida
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Função para extrair conteúdo do PDF
def extract_pdf_data(pdf_path):
    doc = fitz.open(pdf_path)
    content = []
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")  # Extração de texto
        content.append(text)
        
        # Verificar se há imagens (exemplo para ilustrar, se necessário)
        images = page.get_images(full=True)
        for image in images:
            img_bytes = doc.extract_image(image[0])['image']

    return "\n".join(content)

# Função para salvar no banco de dados
def save_to_db(file_id, file_content):
    df = pd.DataFrame({'file_id': [file_id], 'content': [file_content]})
    df.to_sql('pdf_data', con=engine, if_exists='append', index=False)

# Rota principal para upload de arquivos
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo enviado')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('Nenhum arquivo selecionado')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Extrair conteúdo do PDF
            file_content = extract_pdf_data(filepath)
            
            # Gerar um ID único para o arquivo
            file_id = os.path.splitext(filename)[0]
            
            # Salvar conteúdo no banco de dados
            save_to_db(file_id, file_content)
            
            flash('Arquivo processado e salvo com sucesso!')
            return redirect('/')
    
    return render_template('upload.html')

# Nova rota para visualizar os dados salvos no banco de dados
@app.route('/view-data')
def view_data():
    query = "SELECT * FROM pdf_data"
    df = pd.read_sql(query, con=engine)
    
    # Exibir os dados como uma tabela HTML
    return render_template('view_data.html', tables=[df.to_html(classes='data', header=True)], titles=df.columns.values)

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(host='0.0.0.0', port=5000)
