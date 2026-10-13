from manim import *

class VietaScene(Scene):
    def construct(self):
        title=Text("Vieta: roots ↔ coefficients",font_size=42).to_edge(UP)
        f=MathTex(r"(x-r_1)(x-r_2)=x^2-(r_1+r_2)x+r_1r_2",font_size=38)
        v=MathTex(r"r_1+r_2=-\frac ba,\qquad r_1r_2=\frac ca",font_size=38).next_to(f,DOWN,buff=.7)
        self.play(Write(title),Write(f)); self.play(Write(v)); self.wait(2)
        cubic=MathTex(r"x^3-e_1x^2+e_2x-e_3",font_size=46)
        self.play(Transform(f,cubic),FadeOut(v)); self.wait(2)

class QuadraticScene(Scene):
    def construct(self):
        title=Text("Quadratic structure",font_size=42).to_edge(UP)
        d=MathTex(r"\Delta=b^2-4ac",font_size=46)
        labels=VGroup(
            Text("Δ > 0: two real roots",font_size=28),
            Text("Δ = 0: repeated root",font_size=28),
            Text("Δ < 0: conjugate pair",font_size=28)
        ).arrange(DOWN,aligned_edge=LEFT).next_to(d,DOWN,buff=.7)
        self.play(Write(title),Write(d),FadeIn(labels)); self.wait(3)
        self.play(FadeOut(labels))
        nested=MathTex(r"P(P(x))=0:\quad P(y)=0\ \to\ P(x)=y_1\ \text{or}\ y_2",font_size=34).next_to(d,DOWN)
        self.play(Write(nested)); self.wait(2)

class CubicTransformScene(Scene):
    def construct(self):
        title=Text("Cubic transformed roots",font_size=42).to_edge(UP)
        roots=MathTex(r"a,b,c\quad\longrightarrow\quad a+b,\ b+c,\ c+a",font_size=40)
        e1=MathTex(r"E_1=2(a+b+c)",font_size=34).next_to(roots,DOWN,buff=.6)
        e2=MathTex(r"E_2=(a+b)(b+c)+(b+c)(c+a)+(c+a)(a+b)",font_size=30).next_to(e1,DOWN)
        e3=MathTex(r"E_3=(a+b)(b+c)(c+a)",font_size=32).next_to(e2,DOWN)
        self.play(Write(title),Write(roots)); self.play(Write(e1),Write(e2),Write(e3)); self.wait(3)

class BiquadraticScene(Scene):
    def construct(self):
        title=Text("Biquadratic substitution",font_size=42).to_edge(UP)
        q=MathTex(r"Ax^4+Bx^2+C=0",font_size=44)
        sub=MathTex(r"y=x^2",font_size=38).next_to(q,DOWN,buff=.7)
        reduced=MathTex(r"Ay^2+By+C=0",font_size=44).next_to(sub,DOWN,buff=.7)
        self.play(Write(title),Write(q)); self.play(Write(sub),Write(reduced)); self.wait(2)
        back=MathTex(r"y>0\Rightarrow x=\pm\sqrt y",font_size=38).to_edge(DOWN)
        self.play(Write(back)); self.wait(2)

class HigherPolynomialScene(Scene):
    def construct(self):
        title=Text("Higher-degree polynomial strategy",font_size=42).to_edge(UP)
        choices=VGroup(
            Text("Coefficient target → selective extraction",font_size=28),
            Text("Symmetric root target → Vieta",font_size=28),
            Text("Power sum target → Newton identities",font_size=28),
            Text("Shifted variable → binomial/translation",font_size=28),
        ).arrange(DOWN,aligned_edge=LEFT)
        self.play(Write(title),FadeIn(choices)); self.wait(3)
        newton=MathTex(r"p_2=e_1p_1-2e_2,\qquad p_3=e_1p_2-e_2p_1+3e_3",font_size=34).to_edge(DOWN)
        self.play(Write(newton)); self.wait(2)
