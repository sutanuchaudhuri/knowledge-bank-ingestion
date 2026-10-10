from manim import *

class AMGMScene(Scene):
    def construct(self):
        title = Text("AM–GM", font_size=42).to_edge(UP)
        formula = MathTex(r"\frac{a+b}{2}\ge\sqrt{ab}", font_size=46)
        proof = MathTex(r"(\sqrt a-\sqrt b)^2\ge0", font_size=38).next_to(formula, DOWN, buff=.7)
        equality = Text("Equality iff a = b", font_size=28).next_to(proof, DOWN)
        self.play(Write(title), Write(formula))
        self.play(Write(proof), FadeIn(equality))
        self.wait(2)
        self.play(FadeOut(VGroup(title, formula, proof, equality)))
        opt = MathTex(r"a+b=12\Longrightarrow ab\le36,\quad a=b=6", font_size=40)
        self.play(Write(opt)); self.wait(2)

class WeightedAMGMScene(Scene):
    def construct(self):
        title = Text("Weighted AM–GM", font_size=42).to_edge(UP)
        f = MathTex(r"\lambda x+(1-\lambda)y\ge x^\lambda y^{1-\lambda}", font_size=40)
        ex = MathTex(r"\lambda=\frac23:\quad 2x+y\ge3\sqrt[3]{x^2y}", font_size=36).next_to(f, DOWN, buff=.8)
        self.play(Write(title), Write(f)); self.play(Write(ex)); self.wait(3)

class CauchySchwarzScene(Scene):
    def construct(self):
        title = Text("Cauchy–Schwarz", font_size=42).to_edge(UP)
        plane = NumberPlane(x_range=[-1,6,1], y_range=[-1,5,1], x_length=7, y_length=5).shift(DOWN*.3)
        u = Arrow(plane.c2p(0,0), plane.c2p(4,1), buff=0)
        v = Arrow(plane.c2p(0,0), plane.c2p(2,4), buff=0)
        self.play(Write(title), Create(plane), GrowArrow(u), GrowArrow(v))
        geom = MathTex(r"|\langle u,v\rangle|\le\|u\|\|v\|", font_size=36).to_edge(DOWN)
        self.play(Write(geom)); self.wait(2)
        self.play(FadeOut(plane,u,v))
        alg = MathTex(r"\left(\sum a_i b_i\right)^2\le\left(\sum a_i^2\right)\left(\sum b_i^2\right)", font_size=32)
        self.play(Transform(geom,alg)); self.wait(2)

class JensenScene(Scene):
    def construct(self):
        title = Text("Jensen", font_size=42).to_edge(UP)
        axes = Axes(x_range=[-3,3,1], y_range=[0,9,1], x_length=7, y_length=4.5)
        graph = axes.plot(lambda x: x*x, x_range=[-2.5,2.5])
        p1 = Dot(axes.c2p(-2,4)); p2 = Dot(axes.c2p(2,4)); chord = Line(p1.get_center(), p2.get_center())
        self.play(Write(title), Create(axes), Create(graph), FadeIn(p1,p2), Create(chord))
        formula = MathTex(r"f(\lambda x_1+(1-\lambda)x_2)\le\lambda f(x_1)+(1-\lambda)f(x_2)", font_size=29).to_edge(DOWN)
        self.play(Write(formula)); self.wait(3)

class MuirheadScene(Scene):
    def construct(self):
        title = Text("Muirhead & majorization", font_size=42).to_edge(UP)
        a = MathTex(r"\alpha=(4,0,0)", font_size=36).shift(LEFT*2+UP)
        b = MathTex(r"\beta=(2,1,1)", font_size=36).shift(RIGHT*2+UP)
        table = MathTable([["1","4","2"],["2","4","3"],["3","4","4"]],
            col_labels=[MathTex("k"),MathTex(r"\Sigma\alpha"),MathTex(r"\Sigma\beta")],
            include_outer_lines=True).scale(.65).shift(DOWN*.2)
        self.play(Write(title), Write(a), Write(b), Create(table)); self.wait(2)
        conclusion = MathTex(r"(4,0,0)\succ(2,1,1)\Longrightarrow[4,0,0]\ge[2,1,1]", font_size=34).to_edge(DOWN)
        self.play(Write(conclusion)); self.wait(3)
