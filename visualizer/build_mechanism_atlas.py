"""Build the sourced mechanism atlas and concise bilingual README layout."""
from pathlib import Path
from html import escape
import re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/images/mechanisms'
OUT.mkdir(parents=True, exist_ok=True)
notes = (ROOT/'society_probe/society_probe/WORLD_MECHANISM_CANDIDATES_20.md').read_text(encoding='utf-8')
names = ['Renewal','Allee threshold','Consumer–resource','Internal quota','Substrate inhibition','Cross-feeding','Competitive catalysis','Autocatalytic seed','Bistable toggle','Delayed feedback','Nonlinear modulation','Reaction–diffusion','Congested routes','Shared queue','Fatigue & repair','Finite adsorption','Finite buffer','Power-limited storage','Conductance network','Measurement & calibration']
sources = ['Hutchinson · 1948','Dennis · 1989','Holling · 1959','Droop · 1968','Andrews · 1968','Shou et al. · 2007','MIT 5.07SC · 2013','Hordijk et al. · 2012','Gardner et al. · 2000','Hutchinson · 1948','May & Oster · 1976','Turing · 1952','Braess · 1968 / 2005','MIT 2.854 · 2016','Miner · 1945','Langmuir · 1918','MIT 5.111 · 2008','DOE · 2021','Kirkpatrick · 1973','Lindley · 1956']
formulas = [r'\dot R=rR(1-R/K)-h',r'\dot R=rR(1-R/K)(R/A_c-1)-h',r'f(R)=aR/(1+ahR)',r'\mu(Q)=\mu_{max}(1-Q_{min}/Q)_+',r'\mu(S)=\frac{\mu_{max}S}{K_s+S+S^2/K_i}',r'A\rightarrow P+W\quad W+B\rightarrow Q',r'v=\frac{k_{cat}CS}{K_m(1+I/K_i)+S}',r'A+C\rightarrow 2C+W',r'\dot x=\frac{\alpha}{1+y^n}-x',r'z_{t+1}=\rho z_t+\beta u_{t-d}',r'z_{t+1}=\lambda z_t(1-z_t)',r'\dot x_v=f(x_v,y_v)+D\sum_w A_{vw}(x_w-x_v)',r'c_e(f_e)=a_e+b_ef_e',r'Q_{t+1}=\max(0,Q_t+a_t-s_t)',r'D=\sum_k n_k/N_k',r'\theta(c)=Kc/(1+Kc)',r'\mu(z)=\mu_0\max(0,1-|z-z^*|/w)',r'E_{t+1}=\mathrm{clip}_{[0,C]}(E_t+\eta_cp^{in}-p^{out}/\eta_d-\ell)',r'f_{uv}=g_{uv}(V_u-V_v)',r'y=f_\theta(x)+b+\epsilon']
links=[]
for i in range(1,21):
    block = re.search(rf'### {i:02d}\. .*?(?=\n### |\n## |\Z)',notes,re.S).group()
    links.append(re.findall(r'\]\((https?://[^)]+)\)',block)[0])
for i,(name,formula,source) in enumerate(zip(names,formulas,sources),1):
    fig=plt.figure(figsize=(3.6,1.65),facecolor='#f7f5eb')
    fig.text(.06,.83,f'{i:02d}  {name}',fontsize=10,color='#263f37',weight='bold')
    fontsize=12 if len(formula)<65 else 9
    fig.text(.5,.48,'$'+formula+'$',fontsize=fontsize,ha='center',color='#263f37')
    fig.text(.06,.12,source,fontsize=8,color='#718174')
    # A small pixel motif ties the cards to the material-world palette.
    for k in range(3):
        fig.patches.append(plt.Rectangle((.88+k*.025,.13+k*.025),.023,.046,transform=fig.transFigure,color=['#719564','#588ca5','#d5a55b'][k]))
    fig.savefig(OUT/f'{i:02d}.svg',format='svg',facecolor=fig.get_facecolor())
    plt.close(fig)

print('Rendered 20 sourced mechanism cards.')
