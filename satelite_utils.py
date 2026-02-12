from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from io import BytesIO
import base64
import time
import emoji
import os

def inicio(opcao):
    match opcao:
        case"1":
            reg= "AS"
        case"2":
            reg= "BR"
        case"3":
            reg= "CO" 
        case"4":
            reg= "DF"   
        case"5":
            reg= "N"
        case"6":
            reg= "NE"
        case"7":
            reg= "S"
        case"8":
            reg= "SE"
    return reg

def obter_imagem_com_selenium(regiao):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument('--no-sandbox')

    driver = webdriver.Chrome(service=ChromeService(), options=chrome_options)
    driver.get("https://satelite.inmet.gov.br/")
    time.sleep(2)
    WebDriverWait(driver, 15).until(EC.element_to_be_clickable((By.ID, regiao))).click()
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "TN"))).click()
    time.sleep(2)
    img = driver.find_element(By.TAG_NAME, 'img')
    img_src = img.get_attribute('src')
    driver.quit()

    if img_src.startswith("data:image"):
        base64_data = img_src.split(",")[1]
        img_bytes = base64.b64decode(base64_data)
        img_pil = Image.open(BytesIO(img_bytes)).convert("RGB")
    else:
        raise ValueError("A imagem não está em base64. Verifique a URL.")

    return img_pil

def detectar_cores(imagem):
    img_np = np.array(imagem)
    mascara_vermelho = (
        (img_np[:, :, 0] > 180) &
        (img_np[:, :, 1] < 90) &
        (img_np[:, :, 2] < 90)
    )
    mascara_amarelo = (
        (img_np[:, :, 0] > 150) &
        (img_np[:, :, 1] > 152) &
        (img_np[:, :, 2] < 98)
    )
    return mascara_vermelho, mascara_amarelo

def emitir_alerta(imagem, mascara_vermelho, mascara_amarelo):
    img_bgr = cv2.cvtColor(np.array(imagem), cv2.COLOR_RGB2BGR)
    img_pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    kernel = np.ones((6, 6), np.uint8)

    if mascara_vermelho.any():
        mascara_uint8 = (mascara_vermelho.astype(np.uint8)) * 255
        mascara_dilatadaV = cv2.dilate(mascara_uint8, kernel, iterations=1)
        contornos, _ = cv2.findContours(mascara_dilatadaV, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contorno in contornos:
            x, y, w, h = cv2.boundingRect(contorno)
            if w * h < 400:
                continue
            ImageDraw.Draw(img_pil).rectangle([(x, y), (x + w, y + h)], outline=(255, 0, 0), width=6)
            cx = x + w / 2 - 16
            cy = y + h / 2 - 16
            ImageDraw.Draw(img_pil).text((cx, cy), emoji.emojize(":cloud_with_lightning_and_rain:"),
                                         font=ImageFont.truetype("seguiemj.ttf", 35), fill=(255, 255, 255))

    elif not mascara_vermelho.any() and mascara_amarelo.any():
        mascara_uint8 = (mascara_amarelo.astype(np.uint8)) * 255
        mascara_dilatadaA = cv2.dilate(mascara_uint8, kernel, iterations=1)
        contornos, _ = cv2.findContours(mascara_dilatadaA, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contorno in contornos:
            x, y, w, h = cv2.boundingRect(contorno)
            if w * h < 500:
                continue
            ImageDraw.Draw(img_pil).rectangle([(x, y), (x + w, y + h)], outline=(255, 255, 0), width=6)
            cx = x + w / 2 - 16
            cy = y + h / 2 - 16
            ImageDraw.Draw(img_pil).text((cx, cy), emoji.emojize(":cloud_with_rain:"),
                                         font=ImageFont.truetype("seguiemj.ttf", 35), fill=(255, 255, 255))

    img_bgr_final = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    return img_bgr_final