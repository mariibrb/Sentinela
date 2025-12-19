import tkinter as tk
from tkinter import ttk, messagebox

class AppInterface:
    def __init__(self, root):
        self.root = root
        self.root.title("Minha Aplicação")
        self.root.geometry("400x300")
        
        self.setup_ui()

    def setup_ui(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Label de boas-vindas
        self.label = ttk.Label(main_frame, text="Bem-vindo ao Sistema", font=("Helvetica", 12))
        self.label.grid(row=0, column=0, pady=10)
        
        # Botão de Ação
        self.btn_acao = ttk.Button(main_frame, text="Clique Aqui", command=self.on_button_click)
        self.btn_acao.grid(row=1, column=0, pady=5)

    def on_button_click(self):
        messagebox.showinfo("Informação", "Botão clicado com sucesso!")

if __name__ == "__main__":
    root = tk.Tk()
