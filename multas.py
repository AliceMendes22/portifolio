#multa por atraso#
while True:
    dias=input("Você entregou o livro com quantos dias de atraso?")
    try:
        diasint=int(dias)
        break
    except ValueError:
        print("Valor inválido, favor digitar numero inteiro")
if diasint<=3:
    multa=0.5*diasint
elif diasint>=4 & diasint<=7:
    multa=1.00*diasint
else: 
    multa= 2.00*diasint
print("voce deve pagar", multa, "reais de multa")

