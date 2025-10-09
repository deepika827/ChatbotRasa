import streamlit as st
from pathlib import Path
import os
import time
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from bedrock_test import main
import fitz  # PyMuPDF

# Load environment variables
load_dotenv()

# title of the streamlit app
st.title(f""":rainbow[PDF Summarizer]""")

with st.container():
    st.header("Upload your PDF Document")
    # when a file is uploaded it saves the file to the directory, creates a path, and invokes the read_and_summarize function

    uploaded_file = st.file_uploader("Upload a file", type="pdf")

    if uploaded_file is not None:

        save_folder = os.getenv("save_folder")
        if save_folder is None:
            st.error("Environment variable 'save_folder' is not set.")
        else:
            os.makedirs(save_folder, exist_ok=True)
        file_path = Path(save_folder, uploaded_file.name)
        # write the uploaded PDF to the save_folder you specified 
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getvalue())


        if file_path.exists():
            # write a success message saying the file has been successfully saved
            st.success(f'File "{uploaded_file.name}" uploaded successfully!')
            # creates a timer to time the length of the summarization task and starts the timer
            start = time.time()
            # running the summarization task, and outputting the results to the front end
            # st.write(Chunk_and_Summarize(file_path))
        
            st.write(main(file_path))
            #ending the timer 
            end = time.time()
            # using the timer, we calculate the minutes and seconds it took to perform the summarization task
            seconds = int(((end - start) % 60))
            minutes = int((end - start) // 60)
            # string to highlight the amount of time taken to complete the summarization task
            total_time = f"""Time taken to generate a summary:
            Minutes: {minutes} Seconds: {round(seconds, 2)}"""
            with st.sidebar:
                st.header(total_time)
            # removing the PDF that was temporarily saved to perform the summarization task
            os.remove(file_path)
    else:
        st.warning("No file uploaded or file is invalid.")





   

      
       