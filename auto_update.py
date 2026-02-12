"""
auto_update.py - Sistema de auto-update simplificado
"""
import json
import threading
import time
import queue
from datetime import datetime, timedelta
import os
import base64
import cv2

class AutoUpdater:
    """Gerencia atualizações automáticas"""
    
    def __init__(self):
        self.is_running = False
        self.ui_callback = None
        self.config_file = "auto_update_config.json"
        self.config = self.load_config()
        self.event_queue = queue.Queue()
        
        # Inicia processador de eventos
        threading.Thread(target=self._event_processor, daemon=True).start()
    
    def load_config(self):
        """Carrega configurações"""
        default_config = {
            "satelite_updates": [],
            "metar_updates": [],
            "intervalo_padrao": 30,
            "ativo": False
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        
        return default_config
    
    def save_config(self):
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
            intervalo_minutos = self.config.get("intervalo_padrao", 30)
        
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
        self.save_config()
        
        print(f"✅ Satélite configurado: {regiao_nome} a cada {intervalo_minutos}min")
        return True
    
    def add_metar_update(self, icao, intervalo_minutos=None):
        """Adiciona atualização de METAR"""
        if intervalo_minutos is None:
            intervalo_minutos = 15
        
        update = {
            "tipo": "metar",
            "icao": icao,
            "intervalo": intervalo_minutos,
            "ultima_atualizacao": None,
            "proxima_atualizacao": datetime.now().isoformat(),
            "ativo": True
        }
        
        # Remove duplicatas
        self.config["metar_updates"] = [
            u for u in self.config.get("metar_updates", [])
            if not (u.get("tipo") == "metar" and u.get("icao") == icao)
        ]
        
        self.config["metar_updates"].append(update)
        self.config["ativo"] = True
        self.save_config()
        
        print(f"✅ METAR configurado: {icao} a cada {intervalo_minutos}min")
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
    
    def _notificar_ui(self, tipo, dados):
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
            
            self.save_config()
            
            # Notifica UI
            self._notificar_ui("satelite_update", {
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
        """Executa atualização de METAR"""
        try:
            print(f"✈️ Executando update METAR: {icao}")
            
            from metapi import MetarInterpreter
            metar = MetarInterpreter()
            resultado = metar.obter_metar_taf(icao)
            
            # Atualiza timestamp
            agora = datetime.now()
            for update in self.config.get("metar_updates", []):
                if update.get("icao") == icao:
                    update["ultima_atualizacao"] = agora.isoformat()
                    nova_proxima = agora + timedelta(minutes=update["intervalo"])
                    update["proxima_atualizacao"] = nova_proxima.isoformat()
                    break
            
            self.save_config()
            
            # Notifica UI
            self._notificar_ui("metar_update", {
                "icao": icao,
                "hora": agora.strftime('%H:%M:%S'),
                "dados": resultado
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Erro METAR: {e}")
            return False
    
    def check_updates(self):
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
        
        self.save_config()
    
    def start(self):
        """Inicia o serviço de auto-update"""
        if self.is_running:
            return
        
        print("🟢 INICIANDO AUTO-UPDATE SERVICE")
        self.is_running = True
        self.config["ativo"] = True
        self.save_config()
        
        def service_loop():
            print("🔄 Service loop iniciado")
            while self.is_running:
                try:
                    self.check_updates()
                    time.sleep(10)  # Verifica a cada 10 segundos
                except Exception as e:
                    print(f"❌ Erro no service loop: {e}")
                    time.sleep(30)
        
        threading.Thread(target=service_loop, daemon=True).start()
        print("✅ Auto-update service ativo!")
    
    def stop(self):
        """Para o serviço"""
        print("🔴 Parando auto-update service")
        self.is_running = False
        self.config["ativo"] = False
        self.save_config()

# Singleton
_auto_updater_instance = None

def get_auto_updater():
    global _auto_updater_instance
    if _auto_updater_instance is None:
        _auto_updater_instance = AutoUpdater()
        print("✅ AutoUpdater instanciado")
    return _auto_updater_instance