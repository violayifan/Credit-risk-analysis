# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 14:50:33 2020

@author: Wang Yifan
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import math


# get raw data of CDS
# date format %date%month%year
def get_cds(path,date,ticker,currency,docClause):
    #get raw data
    try:
        df_cds=pd.read_csv(path+date+".csv",parse_dates=True,header=1,index_col=0)
    
        #choose col&tickers needed
        spread=[i for i in df_cds.columns if "Spread" in i]
        use_col=["Ticker","ShortName","DocClause","Ccy","Recovery"]+spread
        df_cds_sub=df_cds[use_col][(df_cds["Ticker"].isin(ticker))]
        #transfer data
        df_cds_sub[["Recovery"]+spread]=df_cds_sub[["Recovery"]+spread].applymap(lambda x: float(str(x).replace("%",""))/100)
        # check nan value in recovery rate group by tickers 
        for t in df_cds_sub["Ticker"].unique():
            sub=df_cds_sub[df_cds_sub["Ticker"]==t]
            sub["Recovery"].fillna(sub["Recovery"].mean(),inplace=True)
            df_cds_sub[df_cds_sub["Ticker"]==t]=sub
        #select currency&docClause
        df_cds_sub=df_cds_sub[(df_cds_sub["Ccy"]==currency)\
                               &(df_cds_sub["DocClause"]==docClause)]
        return df_cds_sub
    except:
        return pd.DataFrame()
       
# linear interpolate function
def linear_interp(x1,x2,freq):
    return [x1+n*(x2-x1)/freq for n in range(freq)]
    

# bootscrapping the discount factor accounting to cash-flow frequency
def bootscrapping_df(df_rate,date,freq):
    #zero rate
    rate=df_rate.loc[date].values
    year=np.arange(1/freq,len(rate)+1/freq,1/freq)
    
    rate=np.append(np.array(0),rate).copy()
    rate_bs=[]
    for i in range(1,len(rate)):
        rate_bs.extend(linear_interp(rate[i-1],rate[i],freq))
    rate_bs.append(rate[-1])
    rate_bs=np.array(rate_bs[1:])
    df_bs=np.append(1/(1+rate_bs[:4]*year[:4]),1/(1+rate_bs[4:])**year[4:])
    return df_bs


# calculate survival probability from hazard rate
def survival_prob(sp,freq,maturity,hazard):
    if len(sp)==0:
        return np.array([np.exp(-1/freq*n*hazard)for n in range(1,int(maturity*freq)+1)])
    else:
        end= int(freq*maturity-len(sp))                                                                                                                                                                          
        sp_x=sp[-1]*np.array([np.exp(-1/freq*n*hazard) for n in range(1,end+1)])
        return np.append(sp,sp_x)

# calculate default rate during time interval
def default_prob(sp):
        sp_1=np.append(np.array([1]),sp)    
        return np.array([sp_1[i-1]-sp_1[i] for i in range(1,len(sp_1))])
    
# bootscrapping hazard rate based on market data of CDS spread
def bootscrapping_hazard(spread,freq,recovery,maturity,df,sp):
    # PV premium leg-PV protection leg=0
    hazard=fsolve(lambda x:spread*(1/freq)*(survival_prob(sp,freq,maturity,x).reshape(df.shape)@df)-\
                  (1-recovery)*(default_prob(survival_prob(sp,freq,maturity,x).reshape(df.shape))@df),0.1)[0]
    return hazard


if __name__=='__main__':
    
    #get zero rate from US treasury bill
    df_rate=pd.read_csv("Quandl Zero Curve FED-SVENY.csv",parse_dates=True,header=0,index_col=0)/100
  
    #get cds data
    path="CDSCOMP\V5 CDS Composites-"
    #date list
    day=["0"+str(i) for i in range(1,10)]+[str(i) for i in range(10,32)]
    month=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    year=['0'+str(d) for d in range(1,10)]+[str(d) for d in range(10,19)]
    date_l=[d+m+y for d in day for m in month for y in year]
   
    ticker,currency,docClause=["ODP","lTR","KBH","BBY","HNTINL","MBG","BYD","AES","MWD","GS"\
                               "LIBMUT","NAV","XEL-NRGInc","SBGI","TRWAuto"],'USD',"XR14"
   
    df_hazard=pd.DataFrame()
    for count,date in enumerate(date_l):
        cds=get_cds(path,date,ticker,currency,docClause)
        if len(cds) !=0:
            date=cds.index[0]
            spread=[i for i in cds.columns if "Spread" in i]
            maturity=[float(i[6:-1])/12 if i[-1]=="m" else float(i[6:-1]) for i in spread]
            dic_maturity={k:v for k,v in [(spread[i],maturity[i]) for i in range(len(spread))]}
        
        #ensure the date of discount factor data matches the date of CDS trading
        try:
            df=bootscrapping_df(df_rate,date,freq=4)
        except:
            pass
        
        if len(cds)!= 0 and len(df) != 0:
            df_hazard_sub=pd.DataFrame()
            for i,c in cds.iterrows():
                sp=[]
                dic_hazard_sub={}
                for s,m in dic_maturity.items():            
                    if math.isnan(c[s])== False:
                       hazard=bootscrapping_hazard(c[s],4,c["Recovery"],m,df[:int(m*4)],sp)
                       dic_hazard_sub[s]=hazard
                       sp=survival_prob(sp,4,m,hazard)
                    else:
                        dic_hazard_sub[s]=np.nan
                rst=pd.DataFrame([{"Date":i,"Ticker":c["Ticker"],"ShortName":c["ShortName"]}])
                rst_1=pd.DataFrame([dic_hazard_sub]).T.fillna(method="bfill")         
                if True in rst_1.isnull().values:
                    rst_1.fillna(method='ffill',inplace=True)
                    
                rst=rst.join(rst_1.T,how="right").set_index("Date")
                df_hazard_sub=df_hazard_sub.append(rst)                
            df_hazard=df_hazard.append(df_hazard_sub)
            print(date,"processing {}/{}".format(count,len(date_l)))
    
                   
                   
                   
                   
               
           
        
    



