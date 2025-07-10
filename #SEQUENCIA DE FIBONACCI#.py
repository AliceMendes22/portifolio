#SEQUENCIA DE FIBONACCI#
#0-1-1-2-3-5-8-13-21-34....

fib=[0,1]
indice=int(input("Quantos numero da sequencia de fibonacci voce quer?"))
cont=0
cont=indice
while cont>=len(fib):
    fib.append(fib[-2]+fib[-1])
    cont+=1
    if(indice)==len(fib):
        print("-".join(map(str,fib))," \n")
        respo=input("Deseja outro número? \n S para Sim \n N para não: ")
        resp=respo.lower()
        if(resp=="n"):
            break
        else:
            fib=[0,1]
            indice=int(input("Quantos numero da sequencia de fibonacci voce quer?"))
            cont=0
            cont=indice

           

            
    



