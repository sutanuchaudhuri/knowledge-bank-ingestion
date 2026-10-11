from manim import *

class MarkovPropertyScene(Scene):
    def construct(self):
        title=Text("Markov property",font_size=42).to_edge(UP)
        past=RoundedRectangle(width=3,height=1.2).shift(LEFT*4)
        current=RoundedRectangle(width=3,height=1.2)
        future=RoundedRectangle(width=3,height=1.2).shift(RIGHT*4)
        labels=VGroup(Text("past",font_size=28).move_to(past),
                      Text("current state",font_size=28).move_to(current),
                      Text("next state",font_size=28).move_to(future))
        a1=Arrow(past.get_right(),current.get_left())
        a2=Arrow(current.get_right(),future.get_left())
        formula=MathTex(r"P(X_{n+1}\mid X_n,\ldots,X_0)=P(X_{n+1}\mid X_n)",font_size=32).to_edge(DOWN)
        self.play(Write(title),Create(past),Create(current),Create(future),FadeIn(labels),GrowArrow(a1),GrowArrow(a2))
        self.play(Write(formula));self.wait(3)

class AMCStateCompressionScene(Scene):
    def construct(self):
        title=Text("State compression: AMC 2019",font_size=40).to_edge(UP)
        A=MathTex(r"A=(1,1,1)",font_size=42).shift(LEFT*3)
        B=MathTex(r"B=\text{type }(2,1,0)",font_size=42).shift(RIGHT*3)
        self.play(Write(title),Write(A),Write(B))
        ab=Arrow(A.get_right(),B.get_left(),buff=.2)
        ba=Arrow(B.get_left(),A.get_right(),buff=.2).shift(DOWN*.7)
        lab1=MathTex(r"\frac34").next_to(ab,UP)
        lab2=MathTex(r"\frac14").next_to(ba,DOWN)
        self.play(GrowArrow(ab),GrowArrow(ba),Write(lab1),Write(lab2));self.wait(2)
        pi=MathTex(r"\pi=\left(\frac14,\frac34\right),\qquad \pi P=\pi",font_size=38).to_edge(DOWN)
        self.play(Write(pi));self.wait(2)

class HittingProbabilityScene(Scene):
    def construct(self):
        title=Text("First-step hitting probability",font_size=40).to_edge(UP)
        f=MathTex(r"h_i=\sum_j P_{ij}h_j",font_size=48)
        bounds=MathTex(r"h_{\rm success}=1,\qquad h_{\rm failure}=0",font_size=36).next_to(f,DOWN,buff=.8)
        self.play(Write(title),Write(f),Write(bounds));self.wait(2)
        frog=MathTex(r"h_0=\frac12h_1,\quad h_3=\frac14h_2+\frac14",font_size=34).to_edge(DOWN)
        self.play(Write(frog));self.wait(2)

class TriangleBugScene(Scene):
    def construct(self):
        title=Text("AIME 2003 II #13",font_size=40).to_edge(UP)
        tri=Triangle().scale(2)
        self.play(Write(title),Create(tri))
        rec=MathTex(r"p_{n+1}=\frac12(1-p_n)",font_size=44).to_edge(DOWN)
        self.play(Write(rec));self.wait(2)
        fixed=MathTex(r"p_{n+1}-\frac13=-\frac12\left(p_n-\frac13\right)",font_size=38)
        self.play(Transform(rec,fixed));self.wait(2)

class TransitionMatrixScene(Scene):
    def construct(self):
        title=Text("Transition matrix",font_size=42).to_edge(UP)
        P=MathTex(r"P=\begin{pmatrix}p_{11}&p_{12}\\p_{21}&p_{22}\end{pmatrix}",font_size=48)
        step=MathTex(r"\mu_{n+1}=\mu_nP,\qquad \mu_n=\mu_0P^n",font_size=38).next_to(P,DOWN,buff=.8)
        self.play(Write(title),Write(P),Write(step));self.wait(3)

class StationaryScene(Scene):
    def construct(self):
        title=Text("Stationary distribution",font_size=42).to_edge(UP)
        f=MathTex(r"\pi P=\pi,\qquad \sum_i\pi_i=1",font_size=46)
        self.play(Write(title),Write(f));self.wait(2)
        warning=Text("Stationary does not automatically mean convergence from every start.",font_size=26).to_edge(DOWN)
        self.play(FadeIn(warning));self.wait(3)
