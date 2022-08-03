import streamlit as st
import pandas as pd
from geopy import distance
from numpy import isnan, array, arange
import pyomo.environ as pyEnv
from pyomo.opt import SolverFactory
from geopy.geocoders import Nominatim

# insstruções gerais sobre a utilização da ferramenta
st.sidebar.image('download.png',use_column_width=True)
st.header('Otimização de rota')
st.subheader('''Este programa foi elaborado como parte do trabalho final da disciplina de Pesquisa Operacional 2 da Universidade Federal Fluminense (UFF) e tem como objetivo determinar o menor caminho a ser percorrido pela cooperativa COOTRANITS enquanto faz a coleta de óleo vegetal usado que posteriormente será utilizado para a produção de biodiesel. ''')

st.subheader('''É considerado que cada ponto de coleta de óleo será percorrido uma única vez e que o local de início e fim do trajeto é a sede da COOTRANITS, por conta disso para que o programa seja executado da forma que foi planejado  por favor coloque a sede da COOTRANITS como o primeiro valor da tabela em excel.''' )

st.subheader('''Para isso é preciso fazer o upload de um arquivo excel contendo uma coluna com o nome do estabelecimento e outra coluna com a latitude e longitude do local. É possível obter a latitude e longitude de um local pelo google maps através de dispositivo Android, computador, IPhone ou IPad seguindo o tutorial: https://support.google.com/maps/answer/18539?hl=pt-BR&co=GENIE.Platform%3DAndroid&oco=0 ''')

st.subheader('Faça o upload do arquivo excel:')
uploaded_file=st.file_uploader('.', type='xlsx')

if uploaded_file!=None:

    df=pd.read_excel(uploaded_file, engine='openpyxl')
    df.dropna(inplace=True)

    def cid(x):
        return Nominatim(user_agent="geoapiforcootranits").reverse(x).raw['address']['city']

    df['Cidade']=df['Latitude e Longitude'].apply(cid)
    df['Latitude e Longitude']='('+df['Latitude e Longitude'] + ')'
    st.write(df)
    
    
    cidade=st.radio('Deseja percorrer somente uma cidade?', ('Não','Sim'), key=2)
    
    if cidade == 'Sim':
        lista_cidades=list(df['Cidade'].sort_values().unique())
        cidade_unica=st.radio('Qual cidade?',lista_cidades,key=3)
        df=pd.concat([df.iloc[:1], df[(df['Cidade']==cidade_unica)]]) # independente da cidade a sede da cooperativa estará incluída desde que sigam a instrução 
                                                                      # de colocá-la na primeira linha
        df.drop_duplicates(inplace=True) # caso maricá seja a cidade escolhida é importante que não se repita
        df.reset_index(drop=True,inplace=True)

    if df.shape[0]==1:
        st.write('Sua tabela só tem 1 local, verifique o que pode ter acontecido levando em conta as instruções no início da página.')
    else:
        if st.button("Calcular Rota"):
            matriz_locais=pd.DataFrame(columns=df['Nome do estabelecimento'],index=df['Nome do estabelecimento']) # dataframe vazio que será preenchido com as distâncias entre os pontos
            for j in range(len(df['Nome do estabelecimento'])):
                for i in range(len(df['Nome do estabelecimento'])):        
                    if isnan(matriz_locais[df['Nome do estabelecimento'][i]][df['Nome do estabelecimento'][j]]) ==False: #verificação que pula o loop caso já houver valores de distância 
                        continue                                                                                         #assinalados   
                    lugar_1=eval(df['Latitude e Longitude'][i])
                    lugar_2=eval(df['Latitude e Longitude'][j])
                    
                    # distância absoluta em Km entre os pontos considerando modelo elipsoidal da superfície da Terra 
                    matriz_locais[df['Nome do estabelecimento'][i]][df['Nome do estabelecimento'][j]] = round(distance.distance(lugar_1,lugar_2).km,4) 
                    matriz_locais[df['Nome do estabelecimento'][j]][df['Nome do estabelecimento'][i]] = matriz_locais[df['Nome do estabelecimento'][i]][df['Nome do estabelecimento'][j]]


            matriz=array(matriz_locais,dtype=float)



            n=len(matriz)
            #Modelo
            modelo=pyEnv.ConcreteModel()
            #Indices para os locais
            modelo.M=pyEnv.RangeSet(n)
            modelo.N=pyEnv.RangeSet(n)
            #Indice auxiliar para as restricoes de quebra de ciclo
            modelo.U=pyEnv.RangeSet(2,n)

            #Variavel de decisao xij
            modelo.x=pyEnv.Var(modelo.N,modelo.M,within=pyEnv.Binary)
            #Variavel de decisao auxiliar u
            modelo.u=pyEnv.Var(modelo.N,within=pyEnv.NonNegativeIntegers,bounds=(0,n-1))

            #Matriz de custo cij
            modelo.c=pyEnv.Param(modelo.N,modelo.M,initialize= lambda modelo,i, j:matriz[i-1][j-1])

            ##-------------------------DECLARACAO DA FUNCAO OBJETIVO E RESTRICOES ##----------------##

            def  funcobjetivo(modelo):
                return sum(modelo.x[i,j]*modelo.c[i,j]  for i in modelo.N for j in
                modelo.M)


            modelo.objetivo=pyEnv.Objective(rule=funcobjetivo,sense=pyEnv.
                minimize)

            ##------------------------------------------------------##
            #So sai 1 caminho de cada lugar

            def rulerest1(modelo,j):
                return sum(modelo.x[i,j] for i in modelo.N  if  i!=j)==1

            modelo.rest1=pyEnv.Constraint(modelo.M,rule=rulerest1)
            ##------------------------------------------------------##
            #So entra 1 caminho em cada lugar

            def rulerest2(modelo,i):
                return sum(modelo.x[i,j] for j in modelo.M if j!=i)==1

            modelo.rest2=pyEnv.Constraint(modelo.N,rule=rulerest2)
            ##------------------------------------------------------##
            #Restricao de quebra de ciclos

            def rulerest3(modelo,i,j):
                if  i!=j:
                    return modelo.u[i]-modelo.u[j]+modelo.x[i,j]*n<=n-1
                else:
                #Sim, essa restricao nao diz nada, o solver vai ignora-la
                    return modelo.u[i]-modelo.u[i]==0

            modelo.rest3=pyEnv.Constraint(modelo.U,modelo.N,rule=rulerest3)


            ##-------------------------RESOLUCAO DO MODELO--------------------##
            solver=SolverFactory('gurobi',solver_io='python')
            resultado=solver.solve(modelo,tee=True)
            modelo.objetivo()

            ##-------------------------PRINT DAS VARIAVEIS DE DECISAO ESCOLHIDAS ##----------------##
        
            lista=list(modelo.x.keys())
            ordem=[]
            for i in lista:
                if  modelo.x[i]()!=0 and modelo.x[i]()!= None : # valores com 0 foram caminhos não tomados e com None quando i=j, também não considerados
                    print(i,'--',modelo.x[i]())
                    ordem.append(i)

            def ordenar(list_of_tuples):
                j=0
                k=0
                while list_of_tuples[j][0]!=1:
                    j+=1
                ordem_correta=[]
                ordem_correta.append(1)
                while len(ordem_correta)<len(list_of_tuples)+1:
                    if list_of_tuples[j][1]==list_of_tuples[k][0]:
                        ordem_correta.append(list_of_tuples[j][1])
                        j=k
                        k=0
                    elif len(ordem_correta) - (len(list_of_tuples)+1) == -1 :
                        ordem_correta.append(list_of_tuples[k][1]) 
                        ordem_correta.append(1)
                    else: k+=1
                    
                return ordem_correta

            ordem_correta=ordenar(ordem)

            df_final=pd.DataFrame(columns=['Local','Ordem'],index=arange(0,len(ordem_correta)))
            for i in range(len(ordem_correta)):
                
                df_final['Local'][i]=matriz_locais.index[ordem_correta[i]-1]
                df_final['Ordem'][i]=str(i+1)+'º'
            df_final.set_index('Ordem',inplace=True)
            st.write(df_final)
else: 
    st.write('Faça o upload de arquivo excel nesse formato para prosseguir. O cabeçalho das colunas deve ser escrito da mesma forma que está escrito abaixo')
    df_exemplo=pd.DataFrame(array([['COOTRANITS','-22.943572683413887, -42.98217658848167'],['Restaurante 1', '-22.952472683413887, -42.98324558848167 ']]),
    columns=['Nome do estabelecimento','Latitude e Longitude'])
    blankIndex=[''] * len(df_exemplo)
    df_exemplo.index=blankIndex
    st.write(df_exemplo)
