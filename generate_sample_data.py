"""
Generates a schema-compliant SAMPLE question bank for JUT ReAttempter.

IMPORTANT: This produces synthetic demo data only, following the exact JSON
schema you provided (exam / exam_type / exam_number / exam_id /
question_number / subject / question_type / question_html / question_text /
options / correct_answer / your_answer / solution_html / solution_text).

Replace data/questions.json with your real question bank at any time -- the
Flask app only cares about the schema, not where the questions came from.
"""

import json
import random

random.seed(42)

MATH_TAG = lambda expr: f"<math><mn>{expr}</mn></math>"

def mcq_options(correct_idx, values):
    labels = ["1", "2", "3", "4"]
    opts = []
    for lbl, val in zip(labels, values):
        opts.append({"html": f"{lbl} ) {val}", "text": f"{lbl} ) {val}"})
    return opts, labels[correct_idx]

# ---------------------------------------------------------------------------
# Question templates. Each template is a function(seed) -> dict with keys:
# question_html, question_text, options(optional), correct_answer, solution
# ---------------------------------------------------------------------------

def physics_mcq(i, seed):
    banks = [
        lambda s: dict(
            q=f"A particle moves with uniform acceleration. If it covers {10+s} m in the 1st second and {10+2*s} m in the 2nd second, the acceleration of the particle is",
            vals=[f"{s} m/s²", f"{2*s} m/s²", f"{s/2} m/s²", f"{3*s} m/s²"],
            correct=0,
            sol=f"Using v = u + at and s_n formula, acceleration works out to {s} m/s²."
        ),
        lambda s: dict(
            q=f"The dimensional formula of Planck's constant is same as that of",
            vals=["Angular momentum", "Linear momentum", "Force", "Energy"],
            correct=0,
            sol="Planck's constant h has dimensions [ML²T⁻¹], same as angular momentum."
        ),
        lambda s: dict(
            q=f"A body of mass {1+s%5} kg is projected with a velocity of {20+s} m/s at 45° to the horizontal. The kinetic energy at the highest point is",
            vals=[f"{round(0.5*(1+s%5)*((20+s)*0.707)**2,1)} J", f"{(20+s)} J", f"{s} J", "0 J"],
            correct=0,
            sol="At the highest point only the horizontal component of velocity survives; KE = ½m(vcos45°)²."
        ),
        lambda s: dict(
            q=f"The equivalent resistance of two resistors {2+s%6} Ω and {4+s%6} Ω connected in parallel is",
            vals=[f"{round((2+s%6)*(4+s%6)/((2+s%6)+(4+s%6)),2)} Ω", f"{(2+s%6)+(4+s%6)} Ω", f"{(2+s%6)*(4+s%6)} Ω", "1 Ω"],
            correct=0,
            sol="For parallel resistors, 1/R = 1/R1 + 1/R2."
        ),
        lambda s: dict(
            q="Which of the following is a vector quantity?",
            vals=["Impulse", "Work", "Power", "Temperature"],
            correct=0,
            sol="Impulse = change in momentum, and momentum is a vector quantity."
        ),
        lambda s: dict(
            q=f"A wave has frequency {200+10*s} Hz and wavelength {2+s%3} m. Its speed is",
            vals=[f"{(200+10*s)*(2+s%3)} m/s", f"{(200+10*s)} m/s", f"{(2+s%3)} m/s", "0 m/s"],
            correct=0,
            sol="Speed of a wave v = f × λ."
        ),
        lambda s: dict(
            q="The SI unit of magnetic flux is",
            vals=["Weber", "Tesla", "Henry", "Gauss"],
            correct=0,
            sol="Magnetic flux is measured in Weber (Wb); Tesla is flux density."
        ),
        lambda s: dict(
            q=f"A capacitor of {2+s%4} μF is charged to {10+s} V. The energy stored in it is",
            vals=[f"{round(0.5*(2+s%4)*(10+s)**2/1000,2)} mJ", f"{(2+s%4)*(10+s)} mJ", f"{(10+s)} mJ", "0 mJ"],
            correct=0,
            sol="Energy stored U = ½CV²."
        ),
    ]
    d = banks[i % len(banks)](seed)
    opts, correct_label = mcq_options(d["correct"], d["vals"])
    return {
        "question_html": d["q"],
        "question_text": d["q"],
        "options": opts,
        "correct_answer": correct_label,
        "solution_html": f"Detailed Answer: {d['sol']}",
        "solution_text": f"Detailed Answer: {d['sol']}",
    }


def physics_int(i, seed):
    s = seed
    banks = [
        lambda s: dict(q=f"A stone is dropped from a height of {5*(s%20+1)} m. Taking g = 10 m/s², the time (in seconds) taken to reach the ground is (round to nearest integer)",
                        ans=round((2*5*(s%20+1)/10)**0.5),
                        sol="Using h = ½gt², t = √(2h/g)."),
        lambda s: dict(q=f"Two resistors of {s%10+1} Ω each are connected in series with a {6+s%6} V battery. The current (in amperes, rounded) drawn from the battery is",
                        ans=round((6+s%6)/(2*(s%10+1))) if (2*(s%10+1))!=0 else 1,
                        sol="I = V / R_total, R_total = R1 + R2."),
        lambda s: dict(q=f"The number of significant figures in the measurement {round(0.00204*(s%9+1),5)} is",
                        ans=3,
                        sol="Leading zeros are not significant; trailing digits after the decimal in a measured value are significant, giving 3 significant figures."),
    ]
    d = banks[i % len(banks)](s)
    return {
        "question_html": d["q"],
        "question_text": d["q"],
        "options": [],
        "correct_answer": str(d["ans"]),
        "solution_html": f"Detailed Answer: {d['sol']}",
        "solution_text": f"Detailed Answer: {d['sol']}",
    }


def chem_mcq(i, seed):
    s = seed
    banks = [
        lambda s: dict(q="The hybridization of carbon in diamond is", vals=["sp³", "sp²", "sp", "dsp²"], correct=0,
                        sol="Each carbon in diamond is tetrahedrally bonded to four others, hence sp³ hybridised."),
        lambda s: dict(q="Which of the following has the highest electronegativity?", vals=["Fluorine", "Oxygen", "Nitrogen", "Chlorine"], correct=0,
                        sol="Fluorine is the most electronegative element on the Pauling scale (3.98)."),
        lambda s: dict(q=f"The pH of a {round(0.001*(s%5+1),4)} M solution of a strong monobasic acid is approximately", vals=[f"{round(-1*(0.001*(s%5+1))**0.5,2) if False else round(3 - (s%5)*0.05,2)}", "7", "10", "1"], correct=0,
                        sol="For a strong monobasic acid, pH = -log[H+]."),
        lambda s: dict(q="Which of the following is an example of a Lewis acid?", vals=["BF₃", "NH₃", "H₂O", "OH⁻"], correct=0,
                        sol="BF₃ has an incomplete octet and can accept an electron pair, making it a Lewis acid."),
        lambda s: dict(q="The IUPAC name of CH₃-CHO is", vals=["Ethanal", "Ethanol", "Methanal", "Propanal"], correct=0,
                        sol="CH₃-CHO is acetaldehyde, IUPAC name ethanal."),
        lambda s: dict(q=f"The number of moles in {round(11.2*(s%4+1),2)} L of a gas at STP is", vals=[f"{round((11.2*(s%4+1))/22.4,2)}", "1", "2", "0.5"], correct=0,
                        sol="At STP, 1 mole of gas occupies 22.4 L; moles = volume / 22.4."),
        lambda s: dict(q="Which quantum number determines the shape of an orbital?", vals=["Azimuthal (l)", "Principal (n)", "Magnetic (m)", "Spin (s)"], correct=0,
                        sol="The azimuthal quantum number l determines the subshell/shape of the orbital."),
        lambda s: dict(q="Which of the following is an oxidising agent commonly used in titrations?", vals=["KMnO₄", "NaCl", "H₂O", "CH₄"], correct=0,
                        sol="KMnO₄ is a strong oxidising agent widely used in redox titrations."),
    ]
    d = banks[i % len(banks)](s)
    opts, correct_label = mcq_options(d["correct"], d["vals"])
    return {
        "question_html": d["q"],
        "question_text": d["q"],
        "options": opts,
        "correct_answer": correct_label,
        "solution_html": f"Detailed Answer: {d['sol']}",
        "solution_text": f"Detailed Answer: {d['sol']}",
    }


def chem_int(i, seed):
    s = seed
    banks = [
        lambda s: dict(q=f"The number of moles of electrons required to reduce {1+(s%3)} mole(s) of MnO₄⁻ to Mn²⁺ is",
                        ans=5*(1+(s%3)),
                        sol="MnO₄⁻ → Mn²⁺ involves a 5-electron reduction per mole of MnO₄⁻."),
        lambda s: dict(q=f"The molar mass of a compound is {18*(s%5+1)} g/mol. The number of moles present in {18*(s%5+1)*2} g of the compound is",
                        ans=2,
                        sol="Moles = given mass / molar mass."),
        lambda s: dict(q="The oxidation state of Cr in K₂Cr₂O₇ is (enter positive integer only)",
                        ans=6,
                        sol="Solving for Cr: 2(+1) + 2(x) + 7(-2) = 0 gives x = +6."),
    ]
    d = banks[i % len(banks)](s)
    return {
        "question_html": d["q"],
        "question_text": d["q"],
        "options": [],
        "correct_answer": str(d["ans"]),
        "solution_html": f"Detailed Answer: {d['sol']}",
        "solution_text": f"Detailed Answer: {d['sol']}",
    }


def math_mcq(i, seed):
    s = seed
    banks = [
        lambda s: dict(q=f"If f(x) = x² + {s%5+1}x + {s%3+1}, then f'(0) equals", vals=[f"{s%5+1}", f"{s%3+1}", "0", f"{(s%5+1)+(s%3+1)}"], correct=0,
                        sol="f'(x) = 2x + (s%5+1); at x = 0, f'(0) = s%5+1."),
        lambda s: dict(q=f"The value of the determinant of the 2×2 identity matrix multiplied by {s%4+2} is", vals=[f"{(s%4+2)**2}", f"{s%4+2}", "1", "0"], correct=0,
                        sol="det(kI) for 2x2 matrix = k²·det(I) = k²."),
        lambda s: dict(q=f"The sum of first {s%10+5} terms of the AP 2, 4, 6, ... is", vals=[f"{(s%10+5)*((s%10+5)+1)}", f"{2*(s%10+5)}", f"{(s%10+5)**2}", "0"], correct=0,
                        sol="Sum = n/2 [2a + (n-1)d] with a=2, d=2 gives n(n+1)."),
        lambda s: dict(q="The number of ways to arrange the letters of the word 'MATHS' is", vals=["120", "60", "24", "720"], correct=0,
                        sol="'MATHS' has 5 distinct letters, so 5! = 120 arrangements."),
        lambda s: dict(q=f"If sin θ = {round(0.5+ (s%3)*0.1,1)} and θ is acute, then θ lies in which quadrant?", vals=["First", "Second", "Third", "Fourth"], correct=0,
                        sol="For an acute angle with positive sine, θ lies in the first quadrant."),
        lambda s: dict(q=f"The equation of a line with slope {s%5+1} passing through the origin is", vals=[f"y = {s%5+1}x", f"x = {s%5+1}y", f"y = x + {s%5+1}", f"y = -{s%5+1}x"], correct=0,
                        sol="Line through origin with slope m: y = mx."),
        lambda s: dict(q="The probability of getting an even number on a single roll of a fair die is", vals=["1/2", "1/3", "1/6", "2/3"], correct=0,
                        sol="Favourable outcomes {2,4,6} out of 6, probability = 3/6 = 1/2."),
        lambda s: dict(q=f"lim(x→0) (sin {s%3+1}x)/x equals", vals=[f"{s%3+1}", "1", "0", f"{(s%3+1)*2}"], correct=0,
                        sol="Using the standard limit lim(x→0) sin(kx)/x = k."),
    ]
    d = banks[i % len(banks)](s)
    opts, correct_label = mcq_options(d["correct"], d["vals"])
    return {
        "question_html": d["q"],
        "question_text": d["q"],
        "options": opts,
        "correct_answer": correct_label,
        "solution_html": f"Detailed Answer: {d['sol']}",
        "solution_text": f"Detailed Answer: {d['sol']}",
    }


def math_int(i, seed):
    s = seed
    banks = [
        lambda s: dict(q=f"If the roots of x² - {s%7+5}x + 6 = 0 are α and β, the value of α + β is",
                        ans=s%7+5,
                        sol="Sum of roots = -b/a = coefficient relation, giving α+β = s%7+5."),
        lambda s: dict(q=f"The value of ⁵C₂ + ⁵C₃ is",
                        ans=20,
                        sol="⁵C₂ = 10 and ⁵C₃ = 10, and by Pascal's identity their sum equals ⁶C₃ = 20."),
        lambda s: dict(q=f"The number of real solutions of the equation x² - {s%4+1} = 0 is",
                        ans=2,
                        sol="x² = positive constant always gives exactly 2 real roots."),
    ]
    d = banks[i % len(banks)](s)
    return {
        "question_html": d["q"],
        "question_text": d["q"],
        "options": [],
        "correct_answer": str(d["ans"]),
        "solution_html": f"Detailed Answer: {d['sol']}",
        "solution_text": f"Detailed Answer: {d['sol']}",
    }


SUBJECT_GENERATORS = {
    "Physics": (physics_mcq, physics_int),
    "Chemistry": (chem_mcq, chem_int),
    "Mathematics": (math_mcq, math_int),
}

TEST_NUMBERS = ["01", "02", "03", "04", "05", "06"]

def build_test(exam_number, exam_id):
    questions = []
    qn = 1
    seed_base = int(exam_number) * 97
    for subject in ["Physics", "Chemistry", "Mathematics"]:
        mcq_fn, int_fn = SUBJECT_GENERATORS[subject]
        for i in range(20):
            seed = seed_base + i + qn
            data = mcq_fn(i, seed)
            questions.append({
                "exam": "JEE",
                "exam_type": "JUT",
                "exam_number": exam_number,
                "exam_id": exam_id,
                "question_number": qn,
                "subject": subject,
                "question_type": "MCQ",
                **data,
                "your_answer": "",
            })
            qn += 1
        for i in range(5):
            seed = seed_base + i + qn
            data = int_fn(i, seed)
            questions.append({
                "exam": "JEE",
                "exam_type": "JUT",
                "exam_number": exam_number,
                "exam_id": exam_id,
                "question_number": qn,
                "subject": subject,
                "question_type": "Numerical",
                **data,
                "your_answer": "",
            })
            qn += 1
    return questions


def main():
    all_q = []
    for idx, num in enumerate(TEST_NUMBERS):
        exam_id = 9460 + idx * 37
        all_q.extend(build_test(num, exam_id))
    with open("data/questions.json", "w", encoding="utf-8") as f:
        json.dump(all_q, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(all_q)} questions across {len(TEST_NUMBERS)} JUT tests to data/questions.json")


if __name__ == "__main__":
    main()
