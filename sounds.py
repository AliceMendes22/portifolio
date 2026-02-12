"""
sounds.py - Gerenciamento de sons
"""
import os
from kivy.core.audio import SoundLoader

class SoundManager:
    def __init__(self):
        self.sounds = {}
        self.load_sounds()
    
    def load_sounds(self):
        """Carrega arquivos de som"""
        sound_files = {
            'update': 'sounds/update.wav',
            'alert': 'sounds/alert.wav',
            'error': 'sounds/error.wav',
            'notification': 'sounds/notification.wav'
        }
        
        # Cria diretório de sons se não existir
        if not os.path.exists('sounds'):
            os.makedirs('sounds')
            print("📁 Diretório 'sounds' criado")
            print("⚠️ Adicione arquivos .wav para sons personalizados")
        
        # Tenta carregar sons
        for name, path in sound_files.items():
            if os.path.exists(path):
                self.sounds[name] = SoundLoader.load(path)
                if self.sounds[name]:
                    print(f"✅ Som carregado: {name}")
    
    def play(self, sound_name):
        """Toca um som"""
        if sound_name in self.sounds and self.sounds[sound_name]:
            self.sounds[sound_name].play()
            print(f"🔊 Tocando: {sound_name}")
        else:
            # Fallback para beep do sistema
            self.play_system_beep(sound_name)
    
    def play_system_beep(self, sound_type="update"):
        """Beep do sistema como fallback"""
        try:
            import sys
            if sys.platform == "win32":
                import winsound
                if sound_type == "alert":
                    winsound.Beep(800, 500)
                elif sound_type == "error":
                    winsound.Beep(400, 300)
                else:  # update
                    winsound.Beep(1000, 200)
            else:
                # Linux/Mac
                print("\a")
        except:
            pass