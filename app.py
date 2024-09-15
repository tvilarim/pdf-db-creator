import os
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import pandas as pd
from flask import Flask, request, redirect, render_template, flash
from sqlalchemy import create_engine, text
from werkzeug.utils import secure_filename
import re

# Configurações gerais do Flask e banco de dados
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DATABASE'] = 'sqlite:///pdf_data.db'
app.secret_key = 'supersecretkey'

engine = create_engine(app.config['DATABASE'])

# Função para criar a tabela no banco de dados, caso ainda não exista
def create_table():
    with engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS pdf_data (
                file_id TEXT PRIMARY KEY,
                content TEXT,
                data_inicial TEXT,
                data_final TEXT
            )
        '''))

# Função para verificar extensão permitida
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Função para pré-processar o texto extraído e remover sujeira
def clean_text(text):
    text = re.sub(r'\\n+', ' ', text)  # Substitui múltiplas quebras de linha por espaço
    text = re.sub(r'\n+', ' ', text)   # Substitui quebras de linha reais por espaço
    text = re.sub(r'\s+', ' ', text)   # Remove espaços em branco extras
    text = text.replace('\\', '')      # Remove barras invertidas extras
    return text.strip()                # Remove espaços em branco nas extremidades

# Função para extrair datas do conteúdo do PDF
def extract_dates(text):
    # Regex para datas no formato dd/mm/aaaa
    date_pattern = r'\d{2}/\d{2}/\d{4}'
    
    # Procurar data de início após "Data de início:"
    data_inicial = re.search(r'Data de início:\s*(' + date_pattern + ')', text)
    data_inicial = data_inicial.group(1) if data_inicial else None
    
    # Procurar data de conclusão após "Conclusão Efetiva:"
    data_final = re.search(r'Conclusão Efetiva:\s*(' + date_pattern + ')', text)
    data_final = data_final.group(1) if data_final else None
    
    return data_inicial, data_final

# Função para extrair conteúdo do PDF usando vários métodos (PyMuPDF + OCR)
def extract_pdf_data(pdf_path):
    doc = fitz.open(pdf_path)
    content = []
    
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        
        # Tentar extrair texto em formato linear
        text = page.get_text("text")
        if text.strip():  # Se o texto foi extraído corretamente, adiciona
            content.append(text)
        else:
            # Caso não haja texto ou o texto não seja extraído, tentar extrair por blocos
            blocks = page.get_text("blocks")
            for block in blocks:
                if block[4].strip():  # Extraindo o texto dos blocos
                    content.append(block[4])
        
        # Tentar fazer OCR para áreas onde o texto pode ser imagem
        images = page.get_images(full=True)
        for img_index, image in enumerate(images):
            base_image = doc.extract_image(image[0])
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            # Abrir a imagem extraída com PIL para realizar OCR
            image = Image.open(io.BytesIO(image_bytes))
            ocr_text = pytesseract.image_to_string(image, lang="por")  # Usando OCR com língua portuguesa
            if ocr_text.strip():  # Se o OCR encontrou texto, adiciona ao conteúdo
                content.append(ocr_text)
    
    # Concatenar todo o conteúdo e limpar o texto
    raw_content = "\n".join(content)
    cleaned_content = clean_text(raw_content)
    
    # Extrair datas do texto limpo
    data_inicial, data_final = extract_dates(cleaned_content)
    
    return cleaned_content, data_inicial, data_final

# Função para verificar se o arquivo já existe no banco de dados usando query segura
def file_exists(file_id, file_content):
    query = text("SELECT * FROM pdf_data WHERE file_id = :file_id OR content = :file_content")
    result = pd.read_sql(query, con=engine, params={"file_id": file_id, "file_content": file_content})
    
    return not result.empty

# Função para salvar no banco de dados
def save_to_db(file_id, file_content, data_inicial, data_final):
    if file_exists(file_id, file_content):
        flash('Arquivo já existe no banco de dados e não será salvo novamente.')
    else:
        df = pd.DataFrame({'file_id': [file_id], 'content': [file_content], 'data_inicial': [data_inicial], 'data_final': [data_final]})
        df.to_sql('pdf_data', con=engine, if_exists='append', index=False)
        flash('Arquivo processado e salvo com sucesso!')

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

            # Certifique-se de que o diretório de upload existe
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

            # Salvar o arquivo no diretório correto
            try:
                file.save(filepath)
            except Exception as e:
                flash(f'Erro ao salvar o arquivo: {str(e)}')
                return redirect('/')
            
            # Verificar se o arquivo foi salvo corretamente
            if not os.path.exists(filepath):
                flash(f'Erro ao salvar o arquivo: {filename}')
                return redirect('/')
            
            # Renderizar uma página informando que o processamento está em andamento
            return render_template('processing.html', filename=filename)
    
    return render_template('upload.html')

# Rota para processar o arquivo (separada para permitir exibição do feedback ao usuário)
@app.route('/process_file/<filename>', methods=['GET'])
def process_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # Verificar se o arquivo existe antes de tentar processá-lo
    if not os.path.exists(filepath):
        flash(f'O arquivo {filename} não foi encontrado.')
        return redirect('/')
    
    # Extrair conteúdo e datas do PDF
    file_content, data_inicial, data_final = extract_pdf_data(filepath)
    
    # Gerar um ID único para o arquivo
    file_id = os.path.splitext(filename)[0]
    
    # Salvar conteúdo e datas no banco de dados, se não existir duplicata
    save_to_db(file_id, file_content, data_inicial, data_final)
    
    # Redirecionar para a página de visualização após o processamento
    return redirect('/view-data')

# Rota para visualizar os dados salvos no banco de dados
@app.route('/view-data')
def view_data():
    query = "SELECT * FROM pdf_data"
    df = pd.read_sql(query, con=engine)
    
    # Exibir os dados como uma tabela HTML
    return render_template('view_data.html', tables=[df.to_html(classes='data', header=True)], titles=df.columns.values)

if __name__ == '__main__':
    # Certificar-se de que o diretório de upload existe
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    
    # Criar a tabela se ela não existir
    create_table()
    
    # Rodar o Flask na porta especificada
    app.run(host='0.0.0.0', port=5000, debug=True)
