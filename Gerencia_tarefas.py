#---------------------------definindo as funções------------------------------------------#

def mostrar_menu():
    print("---Bem vindo ao gerenciador de tarefas!---")
    print("Selecione uma opção: ")
    opcoes=["1. Adicionar nova tarefa", "2. Listar todas as tarefas","3. Marcar tarefa como concluída", "4. Remover tarefa", '5. Sair']
    for i in opcoes:
        print(i,"\n")
def carregar_tarefas():
    try:
      with open("tarefas.txt", "r") as arquivo:
         return arquivo.readlines()
    except FileNotFoundError:
         return []
    
def salvar_tarefas(tarefas):
   with open("tarefas.txt", "w") as arquivo:
          arquivo.writelines(tarefas)
   
def add_tarefa():
   newtarefa=input("Digite a nova tarefa: ")
   linha= f"[ ] {newtarefa}\n"
   tarefas=carregar_tarefas()
   tarefas.append(linha)
   salvar_tarefas(tarefas)

def mostrar_tarefas():
    with open("tarefas.txt", "r") as arquivo:
        conteudo=arquivo.read()
        print (conteudo)

def remover_tarefa():
    tarefas=carregar_tarefas()
    if not tarefas:
        print("Não há nenhuma tarefa")
        return
    print(" ----TAREFAS----")
    for i, tarefa in enumerate(tarefas, start=1):
        print(f"{i}.{tarefa.strip()}")
    try:
        indice=int(input("Digite o numero da tarefa que deseja remover: "))
        if 1<= indice<= len(tarefas):
            tarefa_removida=tarefas.pop(indice-1)
            salvar_tarefas(tarefas)
            print("Tarefa removida foi a: ",tarefa_removida.strip())
        else:
            print("Numero invalido!")
    except ValueError:
        print(" ERRO tente dnv")

def concluir_tarefa():
    tarefas=carregar_tarefas()
    if not tarefas:
        print("Não há nenhuma tarefa")
        return
    print(" ----TAREFAS----")
    for i, tarefa in enumerate(tarefas, start=1):
        print(f"{i}.{tarefa.strip()}")
    try:
        indice=int(input("Digite o numero da tarefa que deseja concluir: "))
        if 1<= indice<= len(tarefas):
            tarefa_original=tarefas[indice-1].strip()
            a="[ ]"
            tarefa_original=tarefa_original.removeprefix(a)
            tarefas[indice-1]= f"[X] {tarefa_original}\n"
           
            print(tarefa_original)
            salvar_tarefas(tarefas)
            print(f"Tarefa concluida foi a: {tarefas[indice-1 ].strip()}")
        else:
            print("Numero invalido!")
    except ValueError:
        print(" ERRO tente dnv")


def main():
    while True:
        mostrar_menu()
        op=input("Digite: ")
        if op=="1":
         add_tarefa()
        elif op=="2":
            mostrar_tarefas()
        elif op=="3":
            concluir_tarefa()
        elif op=="4":
            remover_tarefa()
        elif op=="5":
            print("Saindo...")
            break
#-------programa-------#


main()