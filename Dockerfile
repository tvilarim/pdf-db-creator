# Usando uma imagem Python leve
FROM python:3.9-slim

# Atualizar e instalar dependências do sistema necessárias para o Tesseract
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    libleptonica-dev \
    pkg-config \
    poppler-utils \
    && apt-get clean

# Definindo o diretório de trabalho no container
WORKDIR /app

# Copiar o arquivo de requisitos
COPY requirements.txt requirements.txt

# Instalar as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código da aplicação
COPY . .

# Expor a porta 5000 para o Flask
EXPOSE 5000

# Comando para rodar o Flask
CMD ["python", "app.py"]
