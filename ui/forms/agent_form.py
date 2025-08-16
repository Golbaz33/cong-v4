# Fichier : ui/forms/agent_form.py
# Version 6.5 : Correction de l'attribut 'solde' inexistant.

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from utils.config_loader import CONFIG
from ui.widgets.arabic_keyboard import ArabicKeyboard

class AgentForm(tk.Toplevel):
    def __init__(self, parent, manager, agent_id_to_modify=None):
        super().__init__(parent)
        self.parent = parent
        self.manager = manager
        self.agent_id = agent_id_to_modify
        self.is_modification = agent_id_to_modify is not None

        self.annee_exercice = self.manager.get_annee_exercice()

        title = "Modifier un Agent" if self.is_modification else "Ajouter un Agent"
        self.title(title)
        self.grab_set()
        self.resizable(False, False)

        self._create_widgets()

        if self.is_modification:
            self._populate_data()

    def _populate_data(self):
        agent = self.manager.get_agent_by_id(self.agent_id)
        if not agent:
            messagebox.showerror("Erreur", "Agent introuvable.", parent=self)
            self.destroy(); return
        
        self.entry_nom.insert(0, agent.nom)
        self.entry_prenom.insert(0, agent.prenom)
        self.entry_ppr.insert(0, agent.ppr)
        self.combo_grade.set(agent.grade)
        
        # --- CORRECTION ---
        # On n'utilise plus agent.solde. On appelle la méthode qui calcule le total.
        solde_total = agent.get_solde_total_actif()
        self.solde_info_label.config(text=f"Solde total actif : {solde_total:.1f} jours")

    def _create_widgets(self):
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)
        
        ttk.Label(frame, text="Nom:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        nom_frame = ttk.Frame(frame); nom_frame.grid(row=0, column=1, sticky="ew")
        self.entry_nom = ttk.Entry(nom_frame); self.entry_nom.pack(side="left", expand=True, fill="x")
        tk.Button(nom_frame, text="🇸🇦", font=('Arial', 12), command=lambda: ArabicKeyboard(self, self.entry_nom), bd=1).pack(side="left", padx=(5,0))

        ttk.Label(frame, text="Prénom:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        prenom_frame = ttk.Frame(frame); prenom_frame.grid(row=1, column=1, sticky="ew")
        self.entry_prenom = ttk.Entry(prenom_frame); self.entry_prenom.pack(side="left", expand=True, fill="x")
        tk.Button(prenom_frame, text="🇸🇦", font=('Arial', 12), command=lambda: ArabicKeyboard(self, self.entry_prenom), bd=1).pack(side="left", padx=(5,0))
        
        ttk.Label(frame, text="PPR:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.entry_ppr = ttk.Entry(frame); self.entry_ppr.grid(row=2, column=1, sticky="ew")

        ttk.Label(frame, text="Grade:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        grades = CONFIG['ui']['grades']
        self.combo_grade = ttk.Combobox(frame, values=grades, state="readonly"); self.combo_grade.grid(row=3, column=1, sticky="ew")
        if grades: self.combo_grade.set(grades[0])

        solde_frame = ttk.LabelFrame(frame, text="Gestion du Solde"); solde_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=10, padx=5)

        if self.is_modification:
            self.solde_info_label = ttk.Label(solde_frame, text="Calcul du solde en cours...")
            self.solde_info_label.pack(pady=10, padx=10)
        else:
            self.solde_entries = {}
            an_n, an_n1, an_n2 = self.annee_exercice, self.annee_exercice - 1, self.annee_exercice - 2
            ttk.Label(solde_frame, text=f"Solde initial ({an_n2}):").grid(row=0, column=0, sticky="w", padx=5, pady=3)
            self.solde_entries[an_n2] = ttk.Entry(solde_frame); self.solde_entries[an_n2].grid(row=0, column=1, sticky="ew"); self.solde_entries[an_n2].insert(0, "0.0")
            ttk.Label(solde_frame, text=f"Solde initial ({an_n1}):").grid(row=1, column=0, sticky="w", padx=5, pady=3)
            self.solde_entries[an_n1] = ttk.Entry(solde_frame); self.solde_entries[an_n1].grid(row=1, column=1, sticky="ew"); self.solde_entries[an_n1].insert(0, "0.0")
            ttk.Label(solde_frame, text=f"Solde initial ({an_n}):").grid(row=2, column=0, sticky="w", padx=5, pady=3)
            self.solde_entries[an_n] = ttk.Entry(solde_frame); self.solde_entries[an_n].grid(row=2, column=1, sticky="ew"); self.solde_entries[an_n].insert(0, str(CONFIG['conges'].get('solde_annuel_par_defaut', 22.0)))

        btn_frame = ttk.Frame(frame); btn_frame.grid(row=5, columnspan=2, pady=(10, 0))
        ttk.Button(btn_frame, text="Valider", command=self._on_validate).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Annuler", command=self.destroy).pack(side=tk.RIGHT)

    def _on_validate(self):
        try:
            agent_data = {'nom': self.entry_nom.get().strip(), 'prenom': self.entry_prenom.get().strip(), 'ppr': self.entry_ppr.get().strip(), 'grade': self.combo_grade.get()}
            if not all([agent_data['nom'], agent_data['ppr'], agent_data['grade']]):
                raise ValueError("Le nom, le PPR et le grade sont obligatoires.")

            if self.is_modification:
                agent_data['id'] = self.agent_id
                success = self.manager.save_agent(agent_data, is_modification=True)
                message = "Agent modifié avec succès."
            else:
                agent_data['annee_exercice'] = self.annee_exercice; agent_data['soldes'] = {}
                for annee, entry in self.solde_entries.items():
                    solde_val = float(entry.get().replace(",", "."))
                    if solde_val < 0: raise ValueError(f"Le solde pour l'année {annee} ne peut pas être négatif.")
                    agent_data['soldes'][annee] = solde_val
                success = self.manager.save_agent(agent_data, is_modification=False)
                message = "Agent ajouté avec succès."

            if success:
                self.parent.set_status(message); self.parent.refresh_all(self.agent_id); self.destroy()
            else:
                messagebox.showerror("Erreur", f"Le PPR '{agent_data['ppr']}' est déjà utilisé ou une autre erreur est survenue.", parent=self)
        except ValueError as e:
            messagebox.showerror("Erreur de saisie", str(e), parent=self)
        except Exception as e:
            messagebox.showerror("Erreur Inattendue", f"Une erreur est survenue: {e}", parent=self)