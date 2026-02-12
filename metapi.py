import requests
from metar_taf_parser.parser import parser
from metar_taf_parser.model.enum import *
import re
from datetime import datetime
import json
import threading
import time
import queue
from datetime import datetime, timedelta
import os
import base64
import cv2

class MetarInterpreter:
    def __init__(self):
        self.weather_descriptions = {
            'RA': 'Chuva 🌧️', 
            '-RA': 'Chuva leve 🌧️','+RA': 'Chuva forte 🌧️',
            'DZ': 'Chuvisco 🌦️','-DZ': 'Chuvisco leve 🌦️','+DZ': 'Chuvisco Forte 🌦️', 
            'SN': 'Neve ❄️',
            'SG': 'Granizo 🌨️', 'PL': 'Granizo de gelo 🧊', 'GS': 'Granizo pequeno',
            'BR': 'Nevoa úmida 🌫️', 'FG': 'Nevoeiro 😶‍🌫️', 'HZ': 'Névoa seca',
            'FU': 'Fumaça 💨', 'VA': 'Cinzas vulcânicas 🌋', 'DU': 'Poeira 🌪️',
            'SA': 'Areia 🏜️', 'HZ': 'Neblina', 'PY': 'Spray',
            'PO': 'Tempestade de poeira', 'SQ': 'Rajadas de vento 💨',
            'FC': 'Tornado 🌪️', 'TS': 'Trovoada ⚡','TSRA': 'Trovoada com chuva ⚡🌧️','-TSRA': 'Trovoada com chuva leve ⚡🌧️','+TSRA': 'Trovoada com chuva forte ⚡🌧️',
            'SH': 'Pancadas de chuva 🌧️', 'VCTS': 'Trovoada na vizinhança⚡',
            'BC': 'Banco de nevoeiro', 'BL': 'Soprado pelo vento',
            'VCSH': 'Pancada na vizinhança', 'SHRA': 'Pancada de chuva 🌧️', '+SHRA': 'Pancada de chuva forte 🌧️','-SHRA': 'Pancada de chuva leve 🌧️',
        }
    
    def obter_metar_taf(self, icao_code):
        """Obtém METAR e TAF para um aeródromo"""
        try:
            icao = icao_code.upper().strip()
            
            # Obtém METAR
            url_metar = f"https://aviationweather.gov/api/data/metar?ids={icao}"
            response_metar = requests.get(url_metar, timeout=10)
            
            metar_text = response_metar.text.strip() if response_metar.status_code == 200 and response_metar.text.strip() != '' else None
            
            if metar_text:
                return {
                    'sucesso': True,
                    'metar': metar_text,
                    'interpretacao_metar': self.interpretar_metar(metar_text)
                }
            else:
                return {'sucesso': False, 'erro': 'Dados não disponíveis'}
                
        except Exception as e:
            return {'sucesso': False, 'erro': str(e)}
    
    def interpretar_metar(self, metar_text):
        """Interpreta METAR com foco em simplicidade"""
        try:
            # Verificação direta por CAVOK
            if 'CAVOK' in metar_text:
                return self._interpretar_cavok(metar_text)
            else:
                return self._interpretar_simples(metar_text)
            
        except Exception as e:
            return {'erro': f'Erro na interpretação: {str(e)}', 'raw': metar_text}
    
    def _interpretar_cavok(self, metar_text):
        """Interpretação para METAR com CAVOK"""
        info = {'cavok': True, 'condicoes': 'CAVOK - Ceiling and Visibility OK ✅'}
        
        # Extrai informações básicas
        partes = metar_text.split()
        if len(partes) > 0:
            info['aerodromo'] = partes[1]
        
        # Data/hora
        for parte in partes:
            if 'Z' in parte and len(parte) == 7 and parte[:-1].isdigit():
                info['data_hora'] = parte
                break
        
        # Vento (usando abordagem mais simples)
        for parte in partes:
            if 'KT' in parte:
                info['vento'] = self._extrair_vento_simples(parte)
                break
        
        # Temperatura
        for parte in partes:
            if '/' in parte and len(parte) == 5 and parte.replace('/', '').isdigit():
                temp, orvalho = parte.split('/')
                info['temperatura'] = f"{temp}°C"
                info['orvalho'] = f"{orvalho}°C"
                break
        
        # QNH
        for parte in partes:
            if parte.startswith('Q') and parte[1:].isdigit() and len(parte) == 5:
                info['qnh'] = f"{parte[1:]} hPa"
                break
        
        info.update({
            'visibilidade': '10km+ 🌤️',
            'nuvens': 'Sem nuvens abaixo de 5000 pés ☀️'
        })
        
        return info
    
    def _interpretar_simples(self, metar_text):
        """Interpretação simplificada para METAR sem CAVOK"""
        info = {}
        partes = metar_text.split()
    
        if len(partes) > 1:
            info['aerodromo'] = partes[1]
        else:
            info['aerodromo'] = "N/A"
        
        # Data/hora
        for parte in partes:
            if 'Z' in parte and len(parte) == 7 and parte[:-1].isdigit():
                info['data_hora'] = parte
                break
        
        # Vento (abordagem mais tolerante)
        for parte in partes:
            if 'KT' in parte or 'MPS' in parte or 'KMH' in parte:
                info['vento'] = self._extrair_vento_simples(parte)
                break
        
        # Visibilidade (4 dígitos)
        for parte in partes:
            if len(parte) == 4 and parte.isdigit():
                info['visibilidade'] = f"{parte} metros"
                break
        
        # Temperatura
        for parte in partes:
            if '/' in parte and len(parte) == 5 and parte.replace('/', '').isdigit():
                temp, orvalho = parte.split('/')
                info['temperatura'] = f"{temp}°C"
                info['orvalho'] = f"{orvalho}°C"
                break
        
        # QNH
        for parte in partes:
            if parte.startswith('Q') and parte[1:].isdigit() and len(parte) == 5:
                info['qnh'] = f"{parte[1:]} hPa"
                break
        
        # Condições meteorológicas (busca por códigos simples)
        condicoes = []
        for parte in partes:
            if parte in self.weather_descriptions:
                condicoes.append(self.weather_descriptions[parte])
        
        info['condicoes'] = ", ".join(condicoes) if condicoes else "Sem tempo presente significativo"
        
        # Nuvens (busca por prefixos comuns)
        nuvens = []
        for parte in partes:
            if parte.startswith(('FEW', 'SCT', 'BKN', 'OVC', 'VV')):
                nuvens.append(parte)
        
        info['nuvens'] = ", ".join(nuvens) if nuvens else "Sem nuvens significativas"
        
        return info
    
    def _extrair_vento_simples(self, vento_str):
        """Extrai informações de vento de forma simples"""
        if 'VRB' in vento_str:
            return "Vento variável"
        
        # Extrai direção e velocidade
        match = re.search(r'(\d{3})(\d{2,3})(G(\d{2,3}))?', vento_str)
        if match:
            direcao, velocidade, _, rajada = match.groups()
            if rajada:
                return f"Vento de {direcao}° a {velocidade} nós com rajadas de {rajada} nós"
            else:
                return f"Vento de {direcao}° a {velocidade} nós"
        
        return "Informações de vento não disponíveis"

class TAFInterpreter:
    def __init__(self):
        self.weather_descriptions = {
            # COMPOSTAS (mais específicas)
            'TSRA': 'Trovoada com chuva ⛈️',
            '-TSRA': 'Trovoada com chuva leve ⛈️',
            '+TSRA': 'Trovoada com chuva forte ⛈️',
            'TSSN': 'Trovoada com neve ⛈️❄️',
            'TSGR': 'Trovoada com granizo ⛈️🧊',
            'TSGS': 'Trovoada com granizo pequeno ⛈️',
            'TSPL': 'Trovoada com granizo de gelo ⛈️🧊',
            'TSDS': 'Trovoada com tempestade de areia ⛈️🏜️',
            'TSPO': 'Trovoada com tempestade de poeira ⛈️🌪️',
            
            # SIMPLES com intensidade
            'RA': 'Chuva 🌧️',
            '-RA': 'Chuva leve 🌧️',
            '+RA': 'Chuva forte 🌧️',
            'SN': 'Neve ❄️',
            '-SN': 'Neve leve ❄️',
            '+SN': 'Neve forte ❄️',
            'SG': 'Granizo 🌨️',
            'PL': 'Granizo de gelo 🧊',
            'GS': 'Granizo pequeno',
            'DZ': 'Chuvisco 🌦️',
            '-DZ': 'Chuvisco leve 🌦️',
            '+DZ': 'Chuvisco forte 🌦️',
            'UP': 'Precipitação desconhecida',
            'BR': 'Nevoa umida 🌫️',
            'FG': 'Nevoeiro 😶‍🌫️',
            'FU': 'Fumaça 💨',
            'VA': 'Cinzas vulcânicas 🌋',
            'DU': 'Poeira 🌪️',
            'SA': 'Areia 🏜️',
            'HZ': 'Neblina',
            'PY': 'Spray',
            'PO': 'Tempestade de poeira 🌪️',
            'SQ': 'Rajadas de vento 💨',
            'FC': 'Tornado 🌪️',
            'SH': 'Pancadas de chuva 🌧️',
            '-SH': 'Pancadas leves 🌧️',
            '+SH': 'Pancadas fortes 🌧️',
            'SHRA': 'Pancada de chuva 🌧️',
            '+SHRA': 'Pancada de chuva forte 🌧️',
            '-SHRA': 'Pancada de chuva leve 🌧️',
            'BC': 'Banco de nevoeiro',
            'BL': 'Soprado pelo vento',
            'VC': 'Nas proximidades',
            'VCSH': 'Pancada na vizinhança',
            'VCTS': 'Trovoada na vizinhança',
            'TS': 'Trovoada ⚡',
        }
        
        self.cloud_descriptions = {
            'FEW': 'Poucas nuvens (1-2 oitavos)',
            'SCT': 'Nuvens dispersas (3-4 oitavos)',
            'BKN': 'Nublado (5-7 oitavos)',
            'OVC': 'Encoberto (8 oitavos)',
            'VV': 'Teto vertical invisível'
        }
    
    def obter_taf(self, icao_code):
        """Obtém TAF para um aeródromo"""
        try:
            icao = icao_code.upper().strip()
            url = f"https://aviationweather.gov/api/data/taf?ids={icao}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200 and response.text.strip():
                taf_text = response.text.strip()
                return {
                    'sucesso': True,
                    'taf': taf_text,
                    'interpretacao': self.interpretar_taf(taf_text)
                }
            else:
                return {'sucesso': False, 'erro': 'TAF não disponível'}
                
        except Exception as e:
            return {'sucesso': False, 'erro': str(e)}
    
    def interpretar_taf(self, taf_text):
        """Interpreta TAF unindo linhas que pertencem à mesma previsão"""
        try:
            print("🔍 INICIANDO INTERPRETAÇÃO DO TAF")
            print("=" * 50)
        
            # Primeiro, une linhas que foram quebradas erroneamente
            taf_corrigido = self._corrigir_quebras_linha(taf_text)
            
            # Agora divide em blocos lógicos
            blocos = self._dividir_em_blocos_logicos(taf_corrigido)
        
            interpretacao = {
                'aerodromo': self._extrair_aerodromo(blocos[0]),
                'validade': self._extrair_validade(blocos[0]),
                'previsoes': []
            }
        
            # Processa cada bloco completo
            for i, bloco in enumerate(blocos):
                if i == 0:  # Pula o cabeçalho do TAF
                    continue
                
                previsao = self._interpretar_bloco_completo(bloco)
                if previsao:
                    interpretacao['previsoes'].append(previsao)
            
            return interpretacao
        
        except Exception as e:
            print(f"❌ Erro na interpretação: {e}")
            return {'erro': f'Erro na interpretação TAF: {str(e)}', 'raw': taf_text}

    def _corrigir_quebras_linha(self, taf_text):
        """Corrige quebras de linha que separam previsões erroneamente"""
        padroes_continuacao = ['TEMPO', 'PROB', 'BECMG', 'FM']
    
        linhas = taf_text.split('\n')
        linhas_corrigidas = []
        i = 0
    
        while i < len(linhas):
            linha_atual = linhas[i].strip()
        
            if i + 1 < len(linhas):
                linha_seguinte = linhas[i + 1].strip()
            
                # Se a linha seguinte começa com padrão de continuação, une com a atual
                if any(linha_seguinte.startswith(padrao) for padrao in padroes_continuacao):
                    if any(linha_atual.endswith(padrao) for padrao in ['PROB40', 'PROB30', 'PROB']):
                        linha_unida = linha_atual + ' ' + linha_seguinte
                        print(f"🔗 Unindo linhas: '{linha_atual}' + '{linha_seguinte}' = '{linha_unida}'")
                        linhas_corrigidas.append(linha_unida)
                        i += 2  # Pula duas linhas
                        continue
        
            linhas_corrigidas.append(linha_atual)
            i += 1
    
        return '\n'.join(linhas_corrigidas)

    def _dividir_em_blocos_logicos(self, taf_text):
        """Divide o TAF em blocos lógicos completos"""
        linhas = taf_text.split('\n')
        blocos = []
        bloco_atual = []
    
        for linha in linhas:
            linha = linha.strip()
            if not linha:
                continue
            
            # Se é um novo bloco (começa com FM, BECMG, TEMPO, PROB)
            if any(linha.startswith(x) for x in ['FM', 'BECMG', 'TEMPO', 'PROB30', 'PROB40', 'PROB']):
                if bloco_atual:
                    blocos.append(' '.join(bloco_atual))
                bloco_atual = [linha]
            else:
                # Continuação do bloco atual
                bloco_atual.append(linha)
    
        if bloco_atual:
            blocos.append(' '.join(bloco_atual))
    
        return blocos
    
    def cavok(self, texto):
        """Verifica se há CAVOK no texto"""
        return 'CAVOK' in texto
    
    def _interpretar_bloco_completo(self, bloco):
        """Interpreta um bloco completo do TAF"""
        bloco = bloco.upper().strip()
    
        tipo = self._extrair_tipo_previsao(bloco)
        if self.cavok(bloco):
            previsao = {
                'tipo': tipo,
                'periodo': self._extrair_periodo(bloco),
                'vento': self._extrair_vento(bloco),
                'visibilidade': "≥10km (CAVOK)",
                'condicoes': "CAVOK - Ceiling and Visibility OK ✅",
                'nuvens': "Sem nuvens significativas",
                'texto_original': bloco
            }
        else:
            previsao = {
                'tipo': tipo,
                'periodo': self._extrair_periodo(bloco),
                'vento': self._extrair_vento(bloco),
                'visibilidade': self._extrair_visibilidade(bloco),
                'condicoes': self._extrair_condicoes(bloco),
                'nuvens': self._extrair_nuvens(bloco),
                'texto_original': bloco
            }
    
        return previsao
    
    def _extrair_aerodromo(self, texto):
        """Extrai código do aeródromo"""
        match = re.search(r'(?:^|\s)([A-Z]{4})(?:\s|$)', texto)
        return match.group(1) if match else "N/A"
    
    def _extrair_validade(self, texto):
        """Extrai período de validade do TAF"""
        match = re.search(r'(\d{4}/\d{4})', texto)
        if match:
            periodo = match.group(1)
            dia_inicio = periodo[:2]
            hora_inicio = periodo[2:4]
            dia_fim = periodo[5:7]
            hora_fim = periodo[7:9]
            
            # Se os dias são iguais, mostrar apenas horários
            if dia_inicio == dia_fim:
                return f"Das {hora_inicio}Z às {hora_fim}Z (dia {dia_inicio})"
            else:
                return f"Das {hora_inicio}Z (dia {dia_inicio}) às {hora_fim}Z (dia {dia_fim})"
        return "N/A"
    
    def _extrair_tipo_previsao(self, linha):
        """Extrai tipo de previsão da LINHA COMPLETA"""
        linha = linha.upper().strip()
    
        # Ordem CRÍTICA: verifica combinações completas primeiro
        if 'PROB40 TEMPO' in linha:
            return 'PROB40 TEMPO (40% chance temporária) ⚡'
        elif 'PROB30 TEMPO' in linha:
            return 'PROB30 TEMPO (30% chance temporária) ⚡'
        elif 'PROB40' in linha:
            return 'PROB40 (40% chance) 📊'
        elif 'PROB30' in linha:
            return 'PROB30 (30% chance) 📊'
        elif 'FM' in linha:
            return 'FROM (a partir de) 🕒'
        elif 'BECMG' in linha:
            return 'BECOMING (tornando-se) 🔄'
        elif 'TEMPO' in linha:
            return 'TEMPORARY (temporário) ⏱️'
        elif 'PROB' in linha:
            return 'PROBABILITY (probabilidade) 📈'
        else:
            return 'PRINCIPAL (previsão principal) 📍'
    
    def _extrair_periodo(self, texto):
        """Extrai período da previsão - CORRIGIDA para formato DDHH/DDHH"""
        # Formato FMHHMM (FM + hora e minuto) - raro em TAFs
        match_fm = re.search(r'FM(\d{4})', texto)
        if match_fm:
            hora_min = match_fm.group(1)
            return f"A partir das {hora_min[:2]}:{hora_min[2:]}Z"
        
        # Formato DDHH/DDHH (dia+hora) - COMUM em TAFs
        match_periodo = re.search(r'(\d{4})/(\d{4})', texto)
        if match_periodo:
            inicio = match_periodo.group(1)
            fim = match_periodo.group(2)
            
            dia_inicio = inicio[:2]
            hora_inicio = inicio[2:]
            dia_fim = fim[:2]
            hora_fim = fim[2:]
            
            # Formatar para mostrar corretamente
            if dia_inicio == dia_fim:
                return f"Das {hora_inicio}Z às {hora_fim}Z (dia {dia_inicio})"
            else:
                return f"Das {hora_inicio}Z (dia {dia_inicio}) às {hora_fim}Z (dia {dia_fim})"
        
        return "Período não especificado"
    
    def _extrair_vento(self, texto):
        """Extrai informações de vento"""
        # Busca padrões de vento com KT
        match = re.search(r'(\d{3}|VRB)(\d{2,3})(G(\d{2,3}))?KT', texto)
        if match:
            direcao, velocidade, _, rajada = match.groups()
            if rajada:
                return f"Vento de {direcao}° a {velocidade} nós com rajadas de {rajada} nós"
            else:
                return f"Vento de {direcao}° a {velocidade} nós"
        
        # Verifica se há "00000KT" (vento calmo)
        if '00000KT' in texto:
            return "Vento calmo"
        
        return "Vento não especificado"
    
    def _extrair_visibilidade(self, texto):
        try:
            # Remove explicitamente os padrões que causam confusão
            texto_limpo = re.sub(r'\d{5}KT', '', texto)    # Remove vento
            texto_limpo = re.sub(r'VRB\d{2}KT', '', texto_limpo)  # Remove vento variável
            texto_limpo = re.sub(r'\d{6}Z', '', texto_limpo)     # Remove data/hora
            texto_limpo = re.sub(r'\d{4}/\d{4}', '', texto_limpo) # Remove validade
        
            # Agora busca o primeiro grupo de 4 dígitos (visibilidade em metros)
            match = re.search(r'\b(\d{4})\b', texto_limpo)
            if match:
                return f"{match.group(1)} metros"
        
            # Busca visibilidade em milhas (ex: 2SM)
            match_sm = re.search(r'(\d+)(?:\.(\d+))?SM', texto)
            if match_sm:
                if match_sm.group(2):
                    return f"{match_sm.group(1)}.{match_sm.group(2)} milhas"
                else:
                    return f"{match_sm.group(1)} milhas"
        
            # Busca 9999 que é visibilidade ≥ 10km
            if '9999' in texto:
                return "≥10km"
                
            return "Visibilidade não especificada"
        
        except Exception:
            return "Visibilidade não especificada"
    
    def _extrair_condicoes(self, texto):
        """Extrai condições meteorológicas - CORRIGIDA"""
        condicoes = []
        
        # Primeiro, buscar combinações compostas (como TSRA, TSSN, etc.)
        for codigo, descricao in self.weather_descriptions.items():
            # Usar regex para encontrar o código como palavra completa
            if re.search(r'\b' + re.escape(codigo) + r'\b', texto):
                condicoes.append(descricao)
        
        # Se encontrou condições, retorna
        if condicoes:
            return ", ".join(condicoes)
        
        # Se não encontrou condições específicas
        return "Condições normais"
    
    def _extrair_nuvens(self, texto):
        """Extrai informações de nuvens"""
        if self.cavok(texto):
            return "Sem nuvens significativas"
        
        nuvens = []
        # Busca todos os padrões de nuvens
        matches = re.findall(r'(FEW|SCT|BKN|OVC|VV)(\d{3})', texto)
        
        for tipo, altura in matches:
            desc = self.cloud_descriptions.get(tipo, tipo)
            # Converter altura de centenas de pés para pés
            altura_pes = int(altura) * 100
            nuvens.append(f"{desc} a {altura_pes} pés")
        
        return ", ".join(nuvens) if nuvens else "Sem nuvens significativas"
    
class AutoUpdateManager:
    """Gerencia todas as atualizações automáticas (METAR/TAF e Satélite)"""
    
    def __init__(self):
        self.is_running = False
        self.ui_callback = None
        self.config_file = "metapi_auto_update.json"
        self.config = self._load_config()
        self.event_queue = queue.Queue()
        self.metar_interpreter = MetarInterpreter()
        self.taf_interpreter = TAFInterpreter()
        
        # Inicia processador de eventos
        threading.Thread(target=self._event_processor, daemon=True).start()
        
        print("✅ AutoUpdateManager inicializado")
    
    def _load_config(self):
        """Carrega configurações"""
        default_config = {
            "satelite_updates": [],
            "metar_updates": [],
            "intervalo_padrao_satelite": 30,
            "intervalo_padrao_metar": 15,
            "ativo": False
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        
        return default_config
    
    def _save_config(self):
        """Salva configurações"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except:
            pass
    
    def set_ui_callback(self, callback):
        """Define callback para UI"""
        self.ui_callback = callback
    
    def add_satelite_update(self, regiao_nome, regiao_codigo, intervalo_minutos=None):
        """Adiciona atualização de satélite"""
        if intervalo_minutos is None:
            intervalo_minutos = self.config.get("intervalo_padrao_satelite", 30)
        
        update = {
            "tipo": "satelite",
            "nome": regiao_nome,
            "codigo": regiao_codigo,
            "intervalo": intervalo_minutos,
            "ultima_atualizacao": None,
            "proxima_atualizacao": datetime.now().isoformat(),
            "ativo": True
        }
        
        # Remove duplicatas
        self.config["satelite_updates"] = [
            u for u in self.config.get("satelite_updates", [])
            if not (u.get("tipo") == "satelite" and u.get("codigo") == regiao_codigo)
        ]
        
        self.config["satelite_updates"].append(update)
        self.config["ativo"] = True
        self._save_config()
        
        print(f"✅ Satélite configurado: {regiao_nome} a cada {intervalo_minutos}min")
        return True
    
    def add_metar_update(self, icao, intervalo_minutos=None):
        """Adiciona atualização de METAR/TAF"""
        if intervalo_minutos is None:
            intervalo_minutos = self.config.get("intervalo_padrao_metar", 15)
        
        update = {
            "tipo": "metar_taf",
            "icao": icao,
            "intervalo": intervalo_minutos,
            "ultima_atualizacao": None,
            "proxima_atualizacao": datetime.now().isoformat(),
            "ativo": True
        }
        
        # Remove duplicatas
        self.config["metar_updates"] = [
            u for u in self.config.get("metar_updates", [])
            if not (u.get("tipo") == "metar_taf" and u.get("icao") == icao)
        ]
        
        self.config["metar_updates"].append(update)
        self.config["ativo"] = True
        self._save_config()
        
        print(f"✅ METAR/TAF configurado: {icao} a cada {intervalo_minutos}min")
        return True
    
    def _event_processor(self):
        """Processa eventos para UI"""
        while True:
            try:
                event_type, event_data = self.event_queue.get(timeout=1)
                if self.ui_callback:
                    self.ui_callback(event_type, event_data)
            except queue.Empty:
                continue
    
    def _notify_ui(self, tipo, dados):
        """Envia notificação para UI"""
        self.event_queue.put((tipo, dados))
    
    def execute_satelite_update(self, regiao_codigo, regiao_nome):
        """Executa atualização de satélite"""
        try:
            print(f"🛰️ Executando update satélite: {regiao_nome}")
            
            from satelite_utils import inicio, obter_imagem_com_selenium, detectar_cores, emitir_alerta
            
            regiao = inicio(regiao_codigo)
            imagem = obter_imagem_com_selenium(regiao)
            mascara_vermelho, mascara_amarelo = detectar_cores(imagem)
            imagem_alerta = emitir_alerta(imagem, mascara_vermelho, mascara_amarelo)
            
            # Converte para base64 para envio
            _, buffer = cv2.imencode('.jpg', imagem_alerta)
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            
            # Atualiza timestamp
            agora = datetime.now()
            for update in self.config.get("satelite_updates", []):
                if update.get("codigo") == regiao_codigo:
                    update["ultima_atualizacao"] = agora.isoformat()
                    nova_proxima = agora + timedelta(minutes=update["intervalo"])
                    update["proxima_atualizacao"] = nova_proxima.isoformat()
                    break
            
            self._save_config()
            
            # Notifica UI
            self._notify_ui("satelite_update", {
                "regiao": regiao_nome,
                "codigo": regiao_codigo,
                "hora": agora.strftime('%H:%M:%S'),
                "tempestades": bool(mascara_vermelho.any()),
                "chuva": bool(mascara_amarelo.any()),
                "imagem": img_base64
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Erro satélite: {e}")
            return False
    
    def execute_metar_update(self, icao):
        """Executa atualização de METAR/TAF usando as classes já existentes"""
        try:
            print(f"✈️ Executando update METAR/TAF: {icao}")
            
            # Usa os interpretadores já inicializados
            resultado_metar = self.metar_interpreter.obter_metar_taf(icao)
            resultado_taf = self.taf_interpreter.obter_taf(icao)
            
            # Atualiza timestamp
            agora = datetime.now()
            for update in self.config.get("metar_updates", []):
                if update.get("icao") == icao:
                    update["ultima_atualizacao"] = agora.isoformat()
                    nova_proxima = agora + timedelta(minutes=update["intervalo"])
                    update["proxima_atualizacao"] = nova_proxima.isoformat()
                    break
            
            self._save_config()
            
            # Notifica UI com dados completos
            self._notify_ui("metar_update", {
                "icao": icao,
                "hora": agora.strftime('%H:%M:%S'),
                "resultado_metar": resultado_metar,
                "resultado_taf": resultado_taf,
                "metar_texto": resultado_metar.get('metar') if resultado_metar.get('sucesso') else None,
                "taf_texto": resultado_taf.get('taf') if resultado_taf.get('sucesso') else None
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Erro METAR/TAF: {e}")
            return False
    
    def check_and_execute_updates(self):
        """Verifica e executa atualizações pendentes"""
        agora = datetime.now()
        
        # Verifica satélites
        for update in self.config.get("satelite_updates", []):
            if update.get("ativo", True):
                proxima_str = update.get("proxima_atualizacao")
                if proxima_str:
                    try:
                        proxima = datetime.fromisoformat(proxima_str)
                        if agora >= proxima:
                            # Executa em thread separada
                            threading.Thread(
                                target=self.execute_satelite_update,
                                args=(update["codigo"], update["nome"]),
                                daemon=True
                            ).start()
                    except:
                        pass
        
        # Verifica METARs
        for update in self.config.get("metar_updates", []):
            if update.get("ativo", True):
                proxima_str = update.get("proxima_atualizacao")
                if proxima_str:
                    try:
                        proxima = datetime.fromisoformat(proxima_str)
                        if agora >= proxima:
                            # Executa em thread separada
                            threading.Thread(
                                target=self.execute_metar_update,
                                args=(update["icao"],),
                                daemon=True
                            ).start()
                    except:
                        pass
        
        self._save_config()
    
    def start_service(self):
        """Inicia o serviço de auto-update"""
        if self.is_running:
            return
        
        print("🟢 INICIANDO AUTO-UPDATE SERVICE")
        self.is_running = True
        self.config["ativo"] = True
        self._save_config()
        
        def service_loop():
            print("🔄 Service loop iniciado")
            while self.is_running:
                try:
                    self.check_and_execute_updates()
                    time.sleep(10)  # Verifica a cada 10 segundos
                except Exception as e:
                    print(f"❌ Erro no service loop: {e}")
                    time.sleep(30)
        
        threading.Thread(target=service_loop, daemon=True).start()
        print("✅ Auto-update service ativo!")
    
    def stop_service(self):
        """Para o serviço"""
        print("🔴 Parando auto-update service")
        self.is_running = False
        self.config["ativo"] = False
        self._save_config()
    
    def get_status(self):
        """Retorna status do serviço"""
        return {
            "running": self.is_running,
            "ativo": self.config.get("ativo", False),
            "satelite_count": len(self.config.get("satelite_updates", [])),
            "metar_count": len(self.config.get("metar_updates", [])),
            "satelite_updates": self.config.get("satelite_updates", []),
            "metar_updates": self.config.get("metar_updates", [])
        }

# Singleton global
_auto_update_manager = None

def get_auto_update_manager():
    """Retorna a instância única do AutoUpdateManager"""
    global _auto_update_manager
    if _auto_update_manager is None:
        _auto_update_manager = AutoUpdateManager()
        print("✅ AutoUpdateManager instanciado")
    return _auto_update_manager