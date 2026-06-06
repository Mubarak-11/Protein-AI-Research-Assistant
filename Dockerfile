FROM python:3.11-slim

#the directory inside the image
WORKDIR /app

#Copy requirements
COPY requirements.txt   requirements.txt

#build the requirements
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt

#The model and its packages
COPY protein_model/ protein_model/

#fastapi connection, loads the weights, whole folder structure, loads all 
COPY serving/ serving/


#port connection
EXPOSE 8000
CMD ["uvicorn", "serving.app.main:app", "--host", "0.0.0.0", "--port", "8000"]