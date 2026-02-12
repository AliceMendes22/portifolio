from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.label import Label
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.graphics.texture import Texture
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.core.audio import SoundLoader
import cv2
import numpy as np
import base64
from datetime import datetime
from satelite_utils import inicio, obter_imagem_com_selenium, detectar_cores, emitir_alerta
from metapi import MetarInterpreter, TAFInterpreter, get_auto_update_manager
import threading

class Interface(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metar_interpreter = MetarInterpreter()
        self.taf_interpreter = TAFInterpreter()
        self.sound_player = SoundPlayer()
        
        # Configura o auto-update manager
        self.auto_update_manager = get_auto_update_manager()
        self.auto_update_manager.set_ui_callback(self.handle_auto_update)
        
        # Configura atualização periódica da UI
        self.setup_ui_refresh()
        
        # Inicia serviço se configurado
        if self.auto_update_manager.config.get("ativo", False):
            self.auto_update_manager.start_service()
        
        # Variáveis para UI
        self.ui_needs_update = False
        self.pending_updates = []
        
        print("✅ Interface inicializada com auto-update")
    
    def setup_ui_refresh(self):
        """Configura atualização periódica da UI"""
        # Atualiza a UI a cada 50ms quando houver mudanças
        self._last_ui_update = 0
        self._ui_update_pending = False
        
        def periodic_ui_update(dt):
            try:
                # Força redraw de todos os widgets
                if hasattr(self, 'canvas'):
                    self.canvas.ask_update()
                
                # Atualiza widgets específicos se necessário
                if self._ui_update_pending:
                    self._ui_update_pending = False
                    
                    # Força atualização de labels
                    for widget_id in ['temp_label', 'status_metar', 'resultado_metar_taf']:
                        if hasattr(self.ids, widget_id):
                            widget = self.ids[widget_id]
                            if hasattr(widget, 'canvas'):
                                widget.canvas.ask_update()
                    
                    # Força atualização da imagem
                    if hasattr(self.ids, 'image_widget') and self.ids.image_widget.texture:
                        self.ids.image_widget.canvas.ask_update()
            
            except Exception as e:
                print(f"⚠️ Erro no periodic_ui_update: {e}")
        
        # Agenda atualização periódica
        Clock.schedule_interval(periodic_ui_update, 0.05)  # 50ms
    
    @mainthread
    def handle_auto_update(self, tipo, dados):
        """Recebe atualizações automáticas do manager"""
        print(f"🔄 Auto-update recebido: {tipo}")
        
        # Marca que UI precisa atualizar
        self._ui_update_pending = True
        
        # Agenda processamento imediato
        Clock.schedule_once(lambda dt: self._process_auto_update(tipo, dados), 0)
    
    def _process_auto_update(self, tipo, dados):
        """Processa atualização automática"""
        if tipo == "satelite_update":
            self._handle_satelite_auto_update(dados)
        elif tipo == "metar_update":
            self._handle_metar_auto_update(dados)
    
    def _handle_satelite_auto_update(self, dados):
        """Processa atualização automática de satélite"""
        try:
            regiao = dados.get("regiao", "")
            hora = dados.get("hora", "")
            imagem_base64 = dados.get("imagem", "")
            tempestades = dados.get("tempestades", False)
            chuva = dados.get("chuva", False)
            
            # Atualiza imagem
            if imagem_base64:
                img_data = base64.b64decode(imagem_base64)
                nparr = np.frombuffer(img_data, np.uint8)
                img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                buffer = cv2.flip(img_cv, 0).tobytes()
                texture = Texture.create(
                    size=(img_cv.shape[1], img_cv.shape[0]), 
                    colorfmt='bgr'
                )
                texture.blit_buffer(buffer, colorfmt='bgr', bufferfmt='ubyte')
                
                # Atualiza widget de imagem
                self.ids.image_widget.texture = texture
                self.ids.image_widget.canvas.ask_update()  # Força redraw
            
            # Atualiza status com marcação de tempo
            status = f"🛰️ {regiao} atualizado {hora}"
            if tempestades:
                status += " ⚡"
                self.sound_player.play("alert")
            if chuva:
                status += " 🌧️"
                self.sound_player.play("alert")
            
            if not tempestades and not chuva:
                self.sound_player.play("update")
            
            # ATUALIZAÇÃO IMEDIATA DO LABEL
            self.ids.temp_label.text = status
            
            # Força redraw do label
            self.ids.temp_label.canvas.ask_update()
            
            print(f"✅ Satélite atualizado automaticamente: {regiao}")
            
        except Exception as e:
            print(f"❌ Erro ao processar update satélite: {e}")
    
    def _handle_metar_auto_update(self, dados):
        """Processa atualização automática de METAR/TAF"""
        try:
            icao = dados.get("icao", "")
            hora = dados.get("hora", "")
            resultado_metar = dados.get("resultado_metar", {})
            resultado_taf = dados.get("resultado_taf", {})
            
            if resultado_metar.get('sucesso') or resultado_taf.get('sucesso'):
                # Atualiza display
                self._update_display_from_result(resultado_metar, resultado_taf, icao, is_auto_update=True)
                
                # Atualiza status - FORÇA ATUALIZAÇÃO IMEDIATA
                self.ids.temp_label.text = f"✈️ {icao} atualizado {hora}"
                
                # FORÇA REDRAW DO LABEL
                self.ids.temp_label.canvas.ask_update()
                
                # Toca som
                self.sound_player.play("update")
                
                print(f"✅ METAR/TAF atualizado automaticamente: {icao}")
        
        except Exception as e:
            print(f"❌ Erro ao processar update METAR: {e}")
    
    # ============================================
    # FUNÇÕES DE SATÉLITE (apenas exibição)
    # ============================================
    
    def analisar(self, instance):
        """Analisa imagem de satélite (apenas uma vez)"""
        threading.Thread(target=self.processar_imagem, daemon=True).start()
    
    def processar_imagem(self):
        """Processa imagem de satélite em thread separada"""
        self.set_loading(True)
        
        try:
            Clock.schedule_once(lambda dt: setattr(self.ids.image_widget, 'color', (0, 0, 0, 1)))
            
            texto_spinner = self.ids.spinner.text
            if '-' in texto_spinner:
                opcao = texto_spinner.split(' ')[0]
                regiao_nome = texto_spinner.split(' - ')[1]
            else:
                opcao = "1"
                regiao_nome = "América do Sul"
            
            regiao = inicio(opcao)
            imagem = obter_imagem_com_selenium(regiao)
            mascara_vermelho, mascara_amarelo = detectar_cores(imagem)
            imagem_alerta = emitir_alerta(imagem, mascara_vermelho, mascara_amarelo)
            
            Clock.schedule_once(lambda dt: self.exibir_imagem(imagem_alerta))
            
            # Configura auto-update AUTOMÁTICO para satélite
            self.auto_update_manager.add_satelite_update(regiao_nome, opcao, 30)
            
            if not self.auto_update_manager.is_running:
                self.auto_update_manager.start_service()
            
            Clock.schedule_once(lambda dt: setattr(
                self.ids.temp_label, 'text',
                f"✅ {regiao_nome} analisado. Auto-update ativado (30min)"
            ))
            
        except Exception as e:
            Clock.schedule_once(lambda dt: self.mostrar_erro(str(e)))
        finally:
            Clock.schedule_once(lambda dt: self.set_loading(False))
    
    def exibir_imagem(self, imagem_alerta):
        """Exibe imagem processada"""
        buffer = cv2.flip(imagem_alerta, 0).tobytes()
        texture = Texture.create(size=(imagem_alerta.shape[1], imagem_alerta.shape[0]), colorfmt='bgr')
        texture.blit_buffer(buffer, colorfmt='bgr', bufferfmt='ubyte')
        self.ids.image_widget.texture = texture
        self.ids.image_widget.color = (1, 1, 1, 1)
        
        # Força redraw da imagem
        self.ids.image_widget.canvas.ask_update()
    
    def esconder_imagem(self, instance):
        """Esconde a imagem"""
        self.ids.image_widget.texture = None 
        self.ids.image_widget.color = (0, 0, 0, 1)
        self.ids.spinner.text = 'Escolha a região' 
        self.ids.spinner.disabled = False
        self.ids.temp_label.text = "Selecione uma região e clique em Analisar"
        self.ids.temp_label.opacity = 1
        
        # Força redraw
        self.ids.image_widget.canvas.ask_update()
        self.ids.temp_label.canvas.ask_update()
    
    # ============================================
    # FUNÇÕES DE METAR/TAF (apenas busca manual)
    # ============================================
    
    def buscar_metar_taf(self, instance):
        """Busca METAR/TAF manualmente"""
        icao = self.ids.icao_input.text.strip().upper()
    
        if len(icao) != 4:
            self.mostrar_erro_metar("❌ Código ICAO deve ter 4 letras!")
            return
    
        self.ids.icao_input.disabled = True
        self.ids.buscar_btn.disabled = True
        self.ids.status_metar.text = "🔍 Buscando METAR/TAF..." 
    
        threading.Thread(target=self._buscar_manual, args=(icao,), daemon=True).start()
    
    def _buscar_manual(self, icao):
        """Busca manual (apenas uma vez)"""
        try:
            resultado_metar = self.metar_interpreter.obter_metar_taf(icao)
            resultado_taf = self.taf_interpreter.obter_taf(icao)
            
            Clock.schedule_once(
                lambda dt: self.mostrar_resultado_manual(resultado_metar, resultado_taf, icao)
            )
            
            # Configura auto-update automaticamente
            self.auto_update_manager.add_metar_update(icao, 15)
            
            if not self.auto_update_manager.is_running:
                self.auto_update_manager.start_service()
            
        except Exception as e:
            Clock.schedule_once(
                lambda dt: self.mostrar_erro_metar(f"Erro: {str(e)}")
            )
    
    def mostrar_resultado_manual(self, resultado_metar, resultado_taf, icao):
        """Mostra resultado de busca manual"""
        try:
            # Reativa os botões
            self.ids.icao_input.disabled = False
            self.ids.buscar_btn.disabled = False
            
            # Armazena dados atuais
            self._update_display_from_result(resultado_metar, resultado_taf, icao, is_auto_update=False)
            
            # Atualiza status
            self.ids.status_metar.text = f"✅ Busca concluída! Auto-update ativado (15min)"
            
            # Força redraw
            self.ids.status_metar.canvas.ask_update()
            self.ids.resultado_metar_taf.canvas.ask_update()
            
        except Exception as e:
            print(f"❌ Erro em mostrar_resultado_manual: {e}")
            self.ids.status_metar.text = f"❌ Erro: {str(e)[:50]}"
            self.ids.icao_input.disabled = False
            self.ids.buscar_btn.disabled = False
    
    # ============================================
    # FUNÇÕES AUXILIARES DE EXIBIÇÃO
    # ============================================
    
    def _update_display_from_result(self, resultado_metar, resultado_taf, icao, is_auto_update=False):
        """Atualiza display a partir dos resultados"""
        # METAR
        if resultado_metar.get('sucesso'):
            self._update_metar_display(resultado_metar, icao, is_auto_update)
        
        # TAF
        if resultado_taf.get('sucesso'):
            self._update_taf_display(resultado_taf, icao, is_auto_update)
    
    def _update_metar_display(self, resultado_metar, icao, is_auto_update=False):
        """Atualiza exibição do METAR"""
        try:
            metar_data = resultado_metar.get('interpretacao_metar', {})
            
            if is_auto_update:
                prefixo = f"[b]📡 METAR {icao} (AUTO-UPDATE {datetime.now().strftime('%H:%M')})[/b]\n"
            else:
                prefixo = f"[b]📡 METAR {icao}[/b]\n"
            
            texto_metar = prefixo
            texto_metar += f"[i]{resultado_metar.get('metar', '')}[/i]\n\n"
            
            for chave, valor in metar_data.items():
                if not chave.startswith('erro') and valor != "N/A":
                    texto_metar += f"• [b]{chave.upper()}:[/b] {valor}\n"
            
            # Armazena METAR atual
            self.current_metar = texto_metar
            
            # Atualiza display
            if hasattr(self, 'current_taf') and self.current_taf:
                self.ids.resultado_metar_taf.text = texto_metar + "\n" + self.current_taf
            else:
                self.ids.resultado_metar_taf.text = texto_metar
            
            # Força redraw
            self.ids.resultado_metar_taf.canvas.ask_update()
            
        except Exception as e:
            print(f"❌ Erro ao atualizar display METAR: {e}")
    
    def _update_taf_display(self, resultado_taf, icao, is_auto_update=False):
        """Atualiza exibição do TAF"""
        try:
            taf_data = resultado_taf.get('interpretacao', {})
            
            if is_auto_update:
                prefixo = f"[b]📊 TAF {icao} (AUTO-UPDATE {datetime.now().strftime('%H:%M')})[/b]\n"
            else:
                prefixo = f"[b]📊 TAF {icao}[/b]\n"
            
            texto_taf = prefixo
            texto_taf += f"[i]{resultado_taf.get('taf', '')}[/i]\n\n"
            
            texto_taf += f"• [b]AERÓDROMO:[/b] {taf_data.get('aerodromo', 'N/A')}\n"
            texto_taf += f"• [b]VALIDADE:[/b] {taf_data.get('validade', 'N/A')}\n"
            
            if taf_data.get('previsoes'):
                texto_taf += f"\n[b]PREVISÕES ({len(taf_data['previsoes'])}):[/b]\n"
                for i, previsao in enumerate(taf_data['previsoes'], 1):
                    texto_taf += f"\n{i}. [b]{previsao['tipo']}[/b] - {previsao['periodo']}\n"
                    texto_taf += f"   • [b]VENTO:[/b] {previsao['vento']}\n"
                    texto_taf += f"   • [b]VISIBILIDADE:[/b] {previsao['visibilidade']}\n"
                    texto_taf += f"   • [b]CONDIÇÕES:[/b] {previsao['condicoes']}\n"
                    texto_taf += f"   • [b]NUVENS:[/b] {previsao['nuvens']}\n"
            else:
                texto_taf += "\nℹ️ Nenhuma previsão específica\n"
            
            # Armazena TAF atual
            self.current_taf = texto_taf
            
            # Atualiza display
            if hasattr(self, 'current_metar') and self.current_metar:
                self.ids.resultado_metar_taf.text = self.current_metar + "\n" + texto_taf
            else:
                self.ids.resultado_metar_taf.text = texto_taf
            
            # Força redraw
            self.ids.resultado_metar_taf.canvas.ask_update()
            
        except Exception as e:
            print(f"❌ Erro ao atualizar display TAF: {e}")
    
    # ============================================
    # FUNÇÕES AUXILIARES
    # ============================================
    
    def set_loading(self, loading):
        """Ativa/desativa estado de carregamento"""
        self.ids.spinner.disabled = loading
        if loading:
            self.ids.temp_label.text = "Processando..."
        else:
            self.ids.temp_label.opacity = 1
    
    def mostrar_erro(self, mensagem):
        """Mostra mensagem de erro"""
        self.ids.temp_label.text = f"Erro: {mensagem}"
        Clock.schedule_once(lambda dt: setattr(self.ids.temp_label, 'opacity', 0), 5)
    
    def mostrar_erro_metar(self, mensagem):
        """Mostra erro na busca de METAR/TAF"""
        self.ids.resultado_metar_taf.text = mensagem
        self.ids.status_metar.text = "❌ Erro na busca"
        self.ids.icao_input.disabled = False
        self.ids.buscar_btn.disabled = False
    
    def check_auto_updates_status(self, instance=None):
        """Verifica status do auto-update"""
        try:
            status_info = self.auto_update_manager.get_status()
            
            status = "📊 STATUS AUTO-UPDATE:\n"
            status += f"• Serviço: {'🟢 ATIVO' if status_info['running'] else '🔴 PARADO'}\n"
            status += f"• 🛰️ Satélite: {status_info['satelite_count']} região(ões)\n"
            status += f"• ✈️ METAR/TAF: {status_info['metar_count']} aeródromo(s)\n"
            
            if status_info['satelite_count'] > 0:
                for update in status_info['satelite_updates']:
                    status += f"  - {update['nome']}: {update['intervalo']}min\n"
            
            self.ids.temp_label.text = status
            
            # Força redraw
            self.ids.temp_label.canvas.ask_update()
            
        except Exception as e:
            self.ids.temp_label.text = f"❌ Erro: {str(e)[:50]}"

class SoundPlayer:
    """Gerencia sons do aplicativo"""
    def __init__(self):
        self.load_sounds()
    
    def load_sounds(self):
        """Carrega os sons do sistema"""
        pass
    
    def play(self, sound_name):
        """Toca um som específico"""
        try:
            import sys
            if sys.platform == "win32":
                import winsound
                duration = 300
                if sound_name == "update":
                    frequency = 1000
                elif sound_name == "alert":
                    frequency = 800
                    duration = 500
                elif sound_name == "error":
                    frequency = 400
                else:
                    frequency = 1000
                
                winsound.Beep(frequency, duration)
            else:
                print(f"\a")
                
            print(f"🔊 Som tocado: {sound_name}")
            
        except Exception as e:
            print(f"❌ Erro ao tocar som: {e}")

class SateliteApp(App):
    def build(self):
        Window.clearcolor = (0, 0, 0, 1)
        self.title = 'Analisador de Satélite e Meteorologia'
        return Interface()

if __name__ == '__main__':
    SateliteApp().run()