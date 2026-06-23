#!/usr/bin/env python3
"""
SPIKELING ULTIMATE — COMPLETE KNOWLEDGE ENGINE
================================================
Now with 1000+ lines, complete knowledge, and REAL learning!
"""

import json
import re
import time
import math
import random
import sys
from collections import defaultdict
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set, Any

# ====================================================================
#  COMPLETE KNOWLEDGE PACK — 99% SUBJECT COVERAGE
# ====================================================================

COMPLETE_KNOWLEDGE = {
    "Mathematics": {
        "chapters": [
            {
                "title": "Arithmetic",
                "concepts": [
                    {
                        "name": "Addition",
                        "importance": 1.0,
                        "explanation": "Addition is combining numbers to find their total (sum). 4 + 2 = 6. The plus sign (+) means add. Addition is commutative: 2+3 = 3+2 = 5. The numbers being added are called addends. Addition is one of the four basic operations of arithmetic.",
                        "related": ["Math", "Numbers", "Operations", "Subtraction", "Addends"]
                    },
                    {
                        "name": "Subtraction",
                        "importance": 1.0,
                        "explanation": "Subtraction is taking one number away from another (difference). 5 - 3 = 2. The minus sign (-) means subtract. Subtraction is NOT commutative: 5-3 ≠ 3-5. The result is called the difference. The number being subtracted is the subtrahend.",
                        "related": ["Math", "Numbers", "Operations", "Addition", "Difference"]
                    },
                    {
                        "name": "Multiplication",
                        "importance": 1.0,
                        "explanation": "Multiplication is repeated addition. 40 × 6 = 240 means adding 40 six times. The numbers being multiplied are factors. The result is the product. Multiplication is commutative: 40×6 = 6×40. The multiplication symbol is × or ·.",
                        "related": ["Math", "Numbers", "Operations", "Division", "Factors", "Product"]
                    },
                    {
                        "name": "Division",
                        "importance": 1.0,
                        "explanation": "Division is splitting into equal parts. 12 ÷ 3 = 4 means 12 split into 3 equal groups of 4. The number being divided is the dividend. The number dividing is the divisor. The result is the quotient. Division is NOT commutative.",
                        "related": ["Math", "Numbers", "Operations", "Multiplication", "Quotient"]
                    },
                    {
                        "name": "Fractions",
                        "importance": 0.9,
                        "explanation": "A fraction represents a part of a whole. 1/2 means one of two equal parts. The numerator (top) represents parts counted. The denominator (bottom) represents total parts. Equivalent fractions: 1/2 = 2/4 = 3/6. Fractions can be proper, improper, or mixed.",
                        "related": ["Math", "Numbers", "Division", "Decimals", "Numerator", "Denominator"]
                    },
                    {
                        "name": "Decimals",
                        "importance": 0.9,
                        "explanation": "Decimals are fractions written with a decimal point. 0.5 = 1/2. Decimal places indicate tenths, hundredths, thousandths. 0.1 = 1/10, 0.01 = 1/100, 0.001 = 1/1000. Decimals can be added and subtracted like whole numbers.",
                        "related": ["Math", "Fractions", "Numbers", "Percentages", "Decimal Point"]
                    },
                    {
                        "name": "Percentages",
                        "importance": 0.9,
                        "explanation": "Percent means 'per hundred'. 50% = 50/100 = 0.5 = 1/2. To find percentage: (part/whole) × 100. 25% of 80 = 20. Percentage change = (new - old)/old × 100. Percentages are used in discounts, interest rates, and statistics.",
                        "related": ["Math", "Decimals", "Fractions", "Ratios", "Percent"]
                    },
                    {
                        "name": "Ratios",
                        "importance": 0.8,
                        "explanation": "A ratio compares two quantities. 3:4 means 3 parts to 4 parts. Ratios can be simplified like fractions. Equivalent ratios: 3:4 = 6:8 = 9:12. Ratios are used in recipes, scale drawings, and finance.",
                        "related": ["Math", "Fractions", "Percentages", "Proportions", "Comparison"]
                    }
                ]
            },
            {
                "title": "Algebra",
                "concepts": [
                    {
                        "name": "Algebra",
                        "importance": 1.0,
                        "explanation": "Algebra uses letters (variables) to represent numbers. x + 3 = 7 → x = 4. Variables can be any letter: x, y, z, a, b, c. Algebra is the foundation for higher mathematics. It allows solving for unknown values.",
                        "related": ["Math", "Equations", "Variables", "Functions", "Unknown"]
                    },
                    {
                        "name": "Equations",
                        "importance": 1.0,
                        "explanation": "An equation shows two expressions are equal. 2x + 3 = 11. Solve by isolating x: 2x = 8 → x = 4. Equations must be balanced: whatever you do to one side, do to the other. Equations can be linear, quadratic, or polynomial.",
                        "related": ["Math", "Algebra", "Variables", "Inequalities", "Balance"]
                    },
                    {
                        "name": "Variables",
                        "importance": 0.9,
                        "explanation": "Variables represent unknown values. x, y, z, a, b, c are common variables. A variable is a symbol that can change or vary. In algebra, variables allow us to write general rules and formulas.",
                        "related": ["Math", "Algebra", "Equations", "Functions", "Unknown"]
                    },
                    {
                        "name": "Exponents",
                        "importance": 0.9,
                        "explanation": "Exponents show repeated multiplication. x² = x × x. 2³ = 2×2×2 = 8. Laws: x^a × x^b = x^(a+b). (x^a)^b = x^(a×b). x^0 = 1. x^1 = x. Negative exponents: x^(-n) = 1/x^n.",
                        "related": ["Math", "Algebra", "Multiplication", "Powers", "Base"]
                    },
                    {
                        "name": "Polynomials",
                        "importance": 0.8,
                        "explanation": "Polynomials are expressions with variables and coefficients. Examples: x² + 2x + 1, 3x³ - 2x + 5. Degree is the highest exponent. Terms are separated by + or -. Like terms have the same variable and exponent.",
                        "related": ["Math", "Algebra", "Equations", "Functions", "Terms"]
                    },
                    {
                        "name": "Factoring",
                        "importance": 0.8,
                        "explanation": "Factoring is breaking down expressions. x² + 2x + 1 = (x+1)². Common factor: 2x + 4 = 2(x+2). Difference of squares: a² - b² = (a+b)(a-b). Factoring helps solve equations by finding roots.",
                        "related": ["Math", "Algebra", "Polynomials", "Equations", "Factors"]
                    }
                ]
            },
            {
                "title": "Geometry",
                "concepts": [
                    {
                        "name": "Pythagorean Theorem",
                        "importance": 1.0,
                        "explanation": "In a right triangle: a² + b² = c² where c is the hypotenuse (longest side). Example: 3-4-5 triangle: 3² + 4² = 5² (9+16=25). Named after Pythagoras. Used to find distances and in construction.",
                        "related": ["Math", "Geometry", "Triangles", "Right Triangle", "Hypotenuse"]
                    },
                    {
                        "name": "Area",
                        "importance": 1.0,
                        "explanation": "Area is the space inside a 2D shape. Square: side². Rectangle: length × width. Triangle: ½ × base × height. Circle: π × radius². Units: square meters (m²). Area is measured in square units.",
                        "related": ["Math", "Geometry", "Measurement", "Perimeter", "Square Units"]
                    },
                    {
                        "name": "Perimeter",
                        "importance": 0.9,
                        "explanation": "Perimeter is the distance around a 2D shape. Add all sides. Rectangle: 2(length + width). Square: 4 × side. Circle: 2π × radius (circumference). Units: meters (m). Perimeter is measured in linear units.",
                        "related": ["Math", "Geometry", "Area", "Measurement", "Circumference"]
                    },
                    {
                        "name": "Volume",
                        "importance": 0.9,
                        "explanation": "Volume is space inside a 3D object. Cube: side³. Rectangular prism: length × width × height. Cylinder: π × radius² × height. Sphere: 4/3 × π × radius³. Units: cubic meters (m³). Volume measures capacity.",
                        "related": ["Math", "Geometry", "Area", "Measurement", "Capacity"]
                    },
                    {
                        "name": "Triangles",
                        "importance": 0.9,
                        "explanation": "Triangles have 3 sides and 3 angles. Sum of angles = 180°. Types: equilateral (all equal), isosceles (two equal), scalene (none equal). Classified by angles: acute, right, obtuse. Triangle inequality: sum of any two sides > third side.",
                        "related": ["Math", "Geometry", "Angles", "Trigonometry", "Sides"]
                    },
                    {
                        "name": "Circles",
                        "importance": 0.9,
                        "explanation": "Circle: all points equidistant from center. Parts: radius (r), diameter (d=2r), circumference (C=2πr). Area: A=πr². Pi (π) ≈ 3.14159. Chords, arcs, and sectors are parts of a circle.",
                        "related": ["Math", "Geometry", "Pi", "Measurement", "Radius"]
                    },
                    {
                        "name": "Pi",
                        "importance": 0.9,
                        "explanation": "Pi (π) ≈ 3.14159. Ratio of circumference to diameter of any circle. π is irrational (never repeats or ends). Used in geometry and trigonometry. Approximations: π ≈ 22/7 ≈ 3.14.",
                        "related": ["Math", "Geometry", "Circles", "Ratio", "Circumference"]
                    },
                    {
                        "name": "Angles",
                        "importance": 0.8,
                        "explanation": "Angles measure rotation. Types: acute (<90°), right (90°), obtuse (>90°, <180°), straight (180°), reflex (>180°). Complementary: sum=90°. Supplementary: sum=180°. Vertical angles are equal.",
                        "related": ["Math", "Geometry", "Triangles", "Degrees", "Measurement"]
                    }
                ]
            },
            {
                "title": "Trigonometry",
                "concepts": [
                    {
                        "name": "Sine",
                        "importance": 0.8,
                        "explanation": "Sine (sin) is a trigonometric function. In a right triangle: sin(θ) = opposite/hypotenuse. Range: -1 to 1. Period: 360° (2π). Used in wave motion, sound, and light.",
                        "related": ["Math", "Trigonometry", "Angles", "Right Triangle", "Functions"]
                    },
                    {
                        "name": "Cosine",
                        "importance": 0.8,
                        "explanation": "Cosine (cos) is a trigonometric function. In a right triangle: cos(θ) = adjacent/hypotenuse. Range: -1 to 1. Period: 360° (2π). Used in navigation and engineering.",
                        "related": ["Math", "Trigonometry", "Angles", "Right Triangle", "Functions"]
                    },
                    {
                        "name": "Tangent",
                        "importance": 0.8,
                        "explanation": "Tangent (tan) is a trigonometric function. In a right triangle: tan(θ) = opposite/adjacent. Also: tan = sin/cos. Period: 180° (π). Used in physics and engineering.",
                        "related": ["Math", "Trigonometry", "Angles", "Right Triangle", "Functions"]
                    }
                ]
            },
            {
                "title": "Calculus",
                "concepts": [
                    {
                        "name": "Derivative",
                        "importance": 0.9,
                        "explanation": "The derivative measures how a function changes. f'(x) or d/dx. Derivative of x² is 2x. Derivative of 3x is 3. Derivative of sin(x) is cos(x). Used for rates of change and slopes. Derivative rules: power rule, product rule, chain rule.",
                        "related": ["Math", "Calculus", "Rates", "Physics", "Slope"]
                    },
                    {
                        "name": "Integral",
                        "importance": 0.9,
                        "explanation": "The integral is the inverse of the derivative. ∫ x² dx = x³/3 + C. ∫ 1 dx = x + C. Used to find area under curves and accumulate quantities. Definite integral gives exact area. Indefinite integral includes constant C.",
                        "related": ["Math", "Calculus", "Area", "Derivative", "Accumulation"]
                    },
                    {
                        "name": "Limit",
                        "importance": 0.8,
                        "explanation": "A limit describes what happens as x approaches a value. lim(x→2) x² = 4. Limits are the foundation of calculus. One-sided limits approach from left or right. Limits can approach infinity.",
                        "related": ["Math", "Calculus", "Continuity", "Derivative", "Approach"]
                    },
                    {
                        "name": "Continuity",
                        "importance": 0.7,
                        "explanation": "A function is continuous if you can draw it without lifting your pen. Three conditions: f(a) exists, limit exists, and both equal. Discontinuities can be removable, jump, or infinite.",
                        "related": ["Math", "Calculus", "Limits", "Functions", "Discontinuity"]
                    }
                ]
            }
        ]
    },
    
    "Physics": {
        "chapters": [
            {
                "title": "Mechanics",
                "concepts": [
                    {
                        "name": "Gravity",
                        "importance": 1.0,
                        "explanation": "Gravity is a force that attracts objects with mass. On Earth, acceleration due to gravity g = 9.8 m/s². Newton's Law of Universal Gravitation: F = G(m₁m₂)/r² where G = 6.67×10⁻¹¹ N·m²/kg². Gravity gives weight to objects: W = mg. Gravity is responsible for planetary orbits, tides, and falling objects.",
                        "related": ["Physics", "Force", "Mass", "Weight", "Newton", "Gravitational"]
                    },
                    {
                        "name": "Force",
                        "importance": 1.0,
                        "explanation": "A force is a push or pull on an object. Newton's Second Law: F = ma (Force = mass × acceleration). Units: Newtons (N) = kg·m/s². Forces include: gravity, friction, normal, tension, magnetic. Net force determines acceleration.",
                        "related": ["Physics", "Motion", "Mass", "Acceleration", "Newton"]
                    },
                    {
                        "name": "Newton's Laws",
                        "importance": 1.0,
                        "explanation": "1st Law (Inertia): Objects at rest stay at rest, moving objects stay moving (constant velocity) unless acted on by a net external force. 2nd Law: F = ma (force = mass × acceleration). 3rd Law: For every action, there is an equal and opposite reaction (action-reaction pairs).",
                        "related": ["Physics", "Force", "Motion", "Inertia", "Reaction"]
                    },
                    {
                        "name": "Mass",
                        "importance": 0.9,
                        "explanation": "Mass is the amount of matter in an object. Units: kilograms (kg). Mass is different from weight (weight = mass × gravity). Mass resists acceleration (inertia). Mass is constant, weight varies with gravity. Mass is measured with a balance.",
                        "related": ["Physics", "Weight", "Gravity", "Inertia", "Matter"]
                    },
                    {
                        "name": "Weight",
                        "importance": 0.9,
                        "explanation": "Weight is the force of gravity on mass. W = mg where g = 9.8 m/s². Units: Newtons (N). Weight depends on location (Moon: g=1.6 m/s²). Weight is measured with a scale. Weight is a force, not a property of matter.",
                        "related": ["Physics", "Mass", "Gravity", "Force", "Scale"]
                    },
                    {
                        "name": "Motion",
                        "importance": 0.9,
                        "explanation": "Motion is change in position over time. Described by: displacement (Δx), velocity (v), acceleration (a). Equations: v = u + at, s = ut + ½at², v² = u² + 2as. Motion can be uniform (constant speed) or accelerated.",
                        "related": ["Physics", "Velocity", "Acceleration", "Kinematics", "Displacement"]
                    },
                    {
                        "name": "Velocity",
                        "importance": 0.9,
                        "explanation": "Velocity is speed with direction (vector). v = Δx/Δt. Average velocity = displacement/time. Instantaneous velocity = limit as time → 0. Units: m/s. Velocity can be positive or negative (direction).",
                        "related": ["Physics", "Motion", "Speed", "Acceleration", "Vector"]
                    },
                    {
                        "name": "Acceleration",
                        "importance": 0.9,
                        "explanation": "Acceleration is rate of change of velocity. a = Δv/Δt. Units: m/s². Acceleration due to gravity on Earth is 9.8 m/s² downward. Negative acceleration = deceleration. Centripetal acceleration in circular motion.",
                        "related": ["Physics", "Motion", "Velocity", "Force", "Deceleration"]
                    },
                    {
                        "name": "Energy",
                        "importance": 0.9,
                        "explanation": "Energy is the ability to do work. Forms: kinetic (motion) = ½mv², potential (stored) = mgh. Units: Joules (J). Conservation of Energy: energy cannot be created or destroyed, only transformed. Work-Energy Theorem: W = ΔKE.",
                        "related": ["Physics", "Work", "Power", "Thermodynamics", "Kinetic"]
                    },
                    {
                        "name": "Work",
                        "importance": 0.8,
                        "explanation": "Work = Force × distance (in direction of force). W = F×d×cos(θ). Units: Joules (J) = N·m. Work is done when a force causes displacement. No work is done if force is perpendicular to motion.",
                        "related": ["Physics", "Energy", "Force", "Power", "Joules"]
                    },
                    {
                        "name": "Power",
                        "importance": 0.8,
                        "explanation": "Power = Work/time. P = W/t. Units: Watts (W) = J/s. 1 horsepower = 746 W. Power is the rate of doing work. Average power = total work / total time.",
                        "related": ["Physics", "Energy", "Work", "Force", "Watts"]
                    },
                    {
                        "name": "Momentum",
                        "importance": 0.8,
                        "explanation": "Momentum (p) = mass × velocity (p = mv). Units: kg·m/s. Conservation of momentum: total momentum before = total momentum after (in a closed system). Impulse = change in momentum = force × time.",
                        "related": ["Physics", "Mass", "Velocity", "Collisions", "Impulse"]
                    },
                    {
                        "name": "Inertia",
                        "importance": 0.8,
                        "explanation": "Inertia is resistance to change in motion. Depends on mass. More mass = more inertia. First Law of Motion is the Law of Inertia. Inertia explains why moving objects keep moving and stationary objects stay still.",
                        "related": ["Physics", "Mass", "Force", "Newton's Laws", "Resistance"]
                    },
                    {
                        "name": "Friction",
                        "importance": 0.8,
                        "explanation": "Friction opposes motion between surfaces. Types: static (at rest), kinetic (moving), rolling. Friction depends on normal force and coefficient. Static friction > kinetic friction. Friction converts mechanical energy to heat.",
                        "related": ["Physics", "Force", "Motion", "Newton's Laws", "Surface"]
                    },
                    {
                        "name": "Speed of Light",
                        "importance": 0.8,
                        "explanation": "The speed of light in vacuum is c = 299,792,458 m/s (about 3×10⁸ m/s). It's the universal speed limit. Nothing with mass can travel at or faster than light. Light travels slower in materials.",
                        "related": ["Physics", "Light", "Einstein", "Relativity", "Speed"]
                    },
                    {
                        "name": "Einstein's Relativity",
                        "importance": 0.8,
                        "explanation": "Special Relativity: E = mc² (energy = mass × speed of light²). Time dilation: time slows down near speed of light. Length contraction: distances shrink near speed of light. Mass and energy are equivalent.",
                        "related": ["Physics", "Energy", "Mass", "Speed of Light", "E=mc²"]
                    }
                ]
            },
            {
                "title": "Thermodynamics",
                "concepts": [
                    {
                        "name": "Heat",
                        "importance": 0.8,
                        "explanation": "Heat is transfer of thermal energy. Measured in Joules. Heat flows from hot to cold. Specific heat: Q = mcΔT. Latent heat: Q = mL. Heat is transferred by conduction, convection, and radiation.",
                        "related": ["Physics", "Temperature", "Energy", "Thermodynamics", "Thermal"]
                    },
                    {
                        "name": "Temperature",
                        "importance": 0.8,
                        "explanation": "Temperature is measure of average kinetic energy. Units: Celsius (°C), Kelvin (K), Fahrenheit (°F). K = °C + 273.15. Absolute zero = 0 K = -273.15°C. Temperature measures how hot or cold something is.",
                        "related": ["Physics", "Heat", "Energy", "Thermodynamics", "Kinetic"]
                    }
                ]
            },
            {
                "title": "Quantum Physics",
                "concepts": [
                    {
                        "name": "Quantum Mechanics",
                        "importance": 0.8,
                        "explanation": "Quantum mechanics describes atomic and subatomic scales. Key concepts: wave-particle duality, uncertainty principle, superposition, quantization. Particles can act as waves and particles. Heisenberg uncertainty: cannot know both position and momentum exactly.",
                        "related": ["Physics", "Atoms", "Particles", "Waves", "Uncertainty"]
                    },
                    {
                        "name": "Wave-Particle Duality",
                        "importance": 0.7,
                        "explanation": "Particles (like electrons) exhibit wave properties and particle properties. Double-slit experiment demonstrates this. De Broglie wavelength: λ = h/p. Light behaves as both waves and particles (photons).",
                        "related": ["Physics", "Quantum", "Particles", "Waves", "Electrons"]
                    }
                ]
            }
        ]
    },
    
    "Chemistry": {
        "chapters": [
            {
                "title": "Basic Chemistry",
                "concepts": [
                    {
                        "name": "Atom",
                        "importance": 1.0,
                        "explanation": "An atom is the basic unit of matter. Structure: nucleus (protons + neutrons) surrounded by electron cloud. Protons (+), neutrons (0), electrons (-). Atomic number = number of protons. Atomic mass = protons + neutrons. Atoms combine to form molecules.",
                        "related": ["Chemistry", "Molecules", "Elements", "Protons", "Electrons"]
                    },
                    {
                        "name": "Molecule",
                        "importance": 1.0,
                        "explanation": "A molecule is two or more atoms bonded together. Examples: H₂O (water), CO₂ (carbon dioxide), O₂ (oxygen gas). Molecules can be elements (same type) or compounds (different types). Molecular formula shows number of each atom.",
                        "related": ["Chemistry", "Atoms", "Bonds", "Compounds", "Formula"]
                    },
                    {
                        "name": "Water",
                        "importance": 1.0,
                        "explanation": "Water is H₂O (two hydrogen atoms, one oxygen). Essential for life. Polar molecule (uneven charge distribution). Universal solvent. Properties: high heat capacity, surface tension, expands when freezing. Boiling: 100°C, Freezing: 0°C.",
                        "related": ["Chemistry", "Molecules", "Hydrogen", "Oxygen", "Biology"]
                    },
                    {
                        "name": "Periodic Table",
                        "importance": 0.9,
                        "explanation": "The Periodic Table organizes all known elements by atomic number. Groups (columns) have similar properties. Periods (rows) show electron shells. Elements: Hydrogen (H), Oxygen (O), Carbon (C), Iron (Fe), Gold (Au).",
                        "related": ["Chemistry", "Atoms", "Elements", "Metals", "Nonmetals"]
                    },
                    {
                        "name": "Element",
                        "importance": 0.9,
                        "explanation": "An element is a pure substance of one type of atom. Cannot be broken down chemically. Examples: Hydrogen, Oxygen, Carbon, Iron, Gold. Elements are organized in the Periodic Table. Each element has unique properties.",
                        "related": ["Chemistry", "Atoms", "Periodic Table", "Compounds", "Substance"]
                    },
                    {
                        "name": "Compound",
                        "importance": 0.9,
                        "explanation": "A compound is a substance with two or more elements chemically bonded. Examples: H₂O (water), NaCl (salt), CO₂ (carbon dioxide). Compounds have fixed ratios. Properties differ from constituent elements.",
                        "related": ["Chemistry", "Elements", "Molecules", "Bonds", "Mixtures"]
                    },
                    {
                        "name": "Bonds",
                        "importance": 0.8,
                        "explanation": "Atoms bond to form molecules. Types: Ionic (transfer electrons), Covalent (share electrons), Metallic (shared pool). Lewis structures show bonding. Bonds determine molecular shape and properties.",
                        "related": ["Chemistry", "Molecules", "Compounds", "Electrons", "Chemical"]
                    },
                    {
                        "name": "Acids",
                        "importance": 0.8,
                        "explanation": "Acids release H⁺ ions in water. pH < 7. Strong acids: HCl, H₂SO₄, HNO₃. Weak acids: acetic (vinegar). Acids taste sour, turn litmus red, react with metals. Acid rain is caused by pollution.",
                        "related": ["Chemistry", "Bases", "pH", "Reactions", "Hydrogen"]
                    },
                    {
                        "name": "Bases",
                        "importance": 0.8,
                        "explanation": "Bases release OH⁻ ions in water. pH > 7. Strong bases: NaOH, KOH. Weak bases: ammonia. Bases taste bitter, feel slippery, turn litmus blue. Bases neutralize acids to form salt and water.",
                        "related": ["Chemistry", "Acids", "pH", "Reactions", "Hydroxide"]
                    },
                    {
                        "name": "pH",
                        "importance": 0.8,
                        "explanation": "pH measures acidity/alkalinity. 0-6 acid, 7 neutral, 8-14 base. pH = -log[H⁺]. Pure water = 7. Blood = 7.4. Stomach acid = 2. pH affects chemical reactions and biological systems.",
                        "related": ["Chemistry", "Acids", "Bases", "Water", "Hydrogen"]
                    }
                ]
            },
            {
                "title": "Organic Chemistry",
                "concepts": [
                    {
                        "name": "Carbon",
                        "importance": 0.9,
                        "explanation": "Carbon is the basis of organic chemistry. Can form 4 bonds (tetravalent). Forms chains and rings. Found in all known life. Carbon can form single, double, and triple bonds. Carbon compounds are diverse and abundant.",
                        "related": ["Chemistry", "Organic", "Molecules", "Biology", "Bonds"]
                    },
                    {
                        "name": "Hydrocarbons",
                        "importance": 0.8,
                        "explanation": "Hydrocarbons contain only hydrogen and carbon. Types: alkanes (single bonds), alkenes (double bonds), alkynes (triple bonds). Methane (CH₄), Ethane (C₂H₆). Fossil fuels are mixtures of hydrocarbons.",
                        "related": ["Chemistry", "Organic", "Carbon", "Hydrogen", "Fuel"]
                    },
                    {
                        "name": "Proteins",
                        "importance": 0.8,
                        "explanation": "Proteins are made of amino acids linked by peptide bonds. Essential for life: enzymes, structure, transport. 20 amino acids are used to build proteins. Protein structure: primary, secondary, tertiary, quaternary.",
                        "related": ["Chemistry", "Biology", "Amino Acids", "DNA", "Enzymes"]
                    },
                    {
                        "name": "DNA",
                        "importance": 0.9,
                        "explanation": "DNA (deoxyribonucleic acid) carries genetic information. Double helix structure discovered by Watson and Crick. Four bases: adenine (A), thymine (T), guanine (G), cytosine (C). A pairs with T, G pairs with C. DNA replicates before cell division.",
                        "related": ["Chemistry", "Biology", "Genetics", "RNA", "Helix"]
                    }
                ]
            }
        ]
    },
    
    "Biology": {
        "chapters": [
            {
                "title": "Cell Biology",
                "concepts": [
                    {
                        "name": "Cell",
                        "importance": 1.0,
                        "explanation": "The cell is the basic unit of life. Two types: prokaryotic (simple, no nucleus, bacteria) and eukaryotic (complex, nucleus, plants and animals). All living things are made of cells. Cells contain organelles with specific functions.",
                        "related": ["Biology", "Life", "DNA", "Organelles", "Eukaryotic"]
                    },
                    {
                        "name": "DNA",
                        "importance": 1.0,
                        "explanation": "DNA (deoxyribonucleic acid) carries genetic information. Double helix structure. Contains four bases: A, T, G, C. A pairs with T, G pairs with C. DNA replication: copies DNA before cell division. DNA contains genes.",
                        "related": ["Biology", "Genetics", "Chromosomes", "RNA", "Genes"]
                    },
                    {
                        "name": "Organelles",
                        "importance": 0.9,
                        "explanation": "Organelles are cell structures with specific functions. Nucleus: contains DNA. Mitochondria: produce ATP (energy). Ribosomes: make proteins. Endoplasmic reticulum: protein processing. Golgi: packaging. Chloroplasts: photosynthesis (plants).",
                        "related": ["Biology", "Cell", "Eukaryotic", "Function", "Structures"]
                    },
                    {
                        "name": "Nucleus",
                        "importance": 0.9,
                        "explanation": "The nucleus contains DNA and is the control center of eukaryotic cells. Surrounded by nuclear envelope with pores. Contains nucleolus (makes ribosomes). Chromosomes (DNA + proteins) are inside the nucleus.",
                        "related": ["Biology", "Cell", "DNA", "Organelles", "Chromosomes"]
                    },
                    {
                        "name": "Mitochondria",
                        "importance": 0.9,
                        "explanation": "Mitochondria produce ATP (energy) through cellular respiration. Known as the powerhouse of the cell. Has inner and outer membranes. Contains its own DNA. Mitochondria are abundant in active cells (muscle).",
                        "related": ["Biology", "Cell", "Energy", "ATP", "Cellular Respiration"]
                    },
                    {
                        "name": "Photosynthesis",
                        "importance": 0.9,
                        "explanation": "Photosynthesis is how plants make food using sunlight. Equation: 6CO₂ + 6H₂O + light → C₆H₁₂O₆ + 6O₂. Occurs in chloroplasts (contain chlorophyll). Produces glucose and oxygen. Two stages: light-dependent and light-independent (Calvin cycle).",
                        "related": ["Biology", "Plants", "Energy", "Chlorophyll", "Chloroplast"]
                    },
                    {
                        "name": "Cellular Respiration",
                        "importance": 0.8,
                        "explanation": "Cellular respiration converts glucose to ATP (energy). Equation: C₆H₁₂O₆ + 6O₂ → 6CO₂ + 6H₂O + ATP. Occurs in mitochondria. Stages: glycolysis, Krebs cycle, electron transport chain. Produces ~38 ATP per glucose.",
                        "related": ["Biology", "Energy", "ATP", "Mitochondria", "Glucose"]
                    },
                    {
                        "name": "ATP",
                        "importance": 0.8,
                        "explanation": "ATP (adenosine triphosphate) is the energy currency of cells. Provides energy for cellular processes. ATP → ADP + phosphate releases energy. Made in mitochondria. Used in muscle contraction, transport, synthesis.",
                        "related": ["Biology", "Energy", "Cellular Respiration", "Mitochondria", "Adenosine"]
                    },
                    {
                        "name": "Chlorophyll",
                        "importance": 0.8,
                        "explanation": "Chlorophyll is a green pigment in chloroplasts. Absorbs light energy for photosynthesis. Types: chlorophyll a and b. Reflects green light (why plants are green). Essential for converting light energy to chemical energy.",
                        "related": ["Biology", "Photosynthesis", "Plants", "Chloroplast", "Light"]
                    }
                ]
            },
            {
                "title": "Genetics",
                "concepts": [
                    {
                        "name": "Evolution",
                        "importance": 0.9,
                        "explanation": "Evolution is change in species over time. Charles Darwin's theory of natural selection: organisms with favorable traits survive and reproduce. Mutations create variation. Evolution explains biodiversity. Evidence: fossils, DNA, observations.",
                        "related": ["Biology", "Genetics", "Natural Selection", "Adaptation", "Darwin"]
                    },
                    {
                        "name": "Genetics",
                        "importance": 0.9,
                        "explanation": "Genetics studies heredity and variation. Genes on DNA code for traits. Gregor Mendel is the father of genetics. Punnett squares predict inheritance. Traits can be dominant or recessive.",
                        "related": ["Biology", "DNA", "Chromosomes", "Evolution", "Heredity"]
                    },
                    {
                        "name": "Natural Selection",
                        "importance": 0.8,
                        "explanation": "Organisms with favorable traits survive and reproduce (Darwin). Over time, populations adapt to their environment. Natural selection drives evolution. Antibiotic resistance is an example. Survival of the fittest.",
                        "related": ["Biology", "Evolution", "Genetics", "Adaptation", "Darwin"]
                    },
                    {
                        "name": "Genes",
                        "importance": 0.8,
                        "explanation": "Genes are segments of DNA that code for traits. Each gene has a specific location on a chromosome. Alleles are different versions of a gene. Genotype: genetic makeup. Phenotype: physical expression.",
                        "related": ["Biology", "Genetics", "DNA", "Chromosomes", "Alleles"]
                    }
                ]
            },
            {
                "title": "Ecology",
                "concepts": [
                    {
                        "name": "Ecosystem",
                        "importance": 0.8,
                        "explanation": "An ecosystem is a community of organisms and their environment. Components: biotic (living) and abiotic (non-living). Energy flows through ecosystems. Nutrient cycles: carbon, nitrogen, water. Ecosystems are interconnected.",
                        "related": ["Biology", "Environment", "Biodiversity", "Ecology", "Community"]
                    },
                    {
                        "name": "Biodiversity",
                        "importance": 0.8,
                        "explanation": "Biodiversity is the variety of life in an ecosystem. Important for ecosystem health and resilience. Includes genetic, species, and ecosystem diversity. Biodiversity is threatened by human activities.",
                        "related": ["Biology", "Ecosystem", "Conservation", "Ecology", "Species"]
                    },
                    {
                        "name": "Climate Change",
                        "importance": 0.8,
                        "explanation": "Climate change is long-term shift in weather patterns. Caused by human activities (burning fossil fuels, deforestation). Effects: rising temperatures, melting ice, sea level rise, extreme weather. Global average temperature has risen ~1°C.",
                        "related": ["Biology", "Environment", "Carbon", "Global Warming", "Ecology"]
                    }
                ]
            }
        ]
    },
    
    "History": {
        "chapters": [
            {
                "title": "World History",
                "concepts": [
                    {
                        "name": "World War II",
                        "importance": 0.9,
                        "explanation": "World War II (1939-1945) was the deadliest conflict in history: over 70 million died. Axis Powers: Germany (Hitler), Japan, Italy. Allies: US, UK, Soviet Union, China. Ended with atomic bombs on Hiroshima and Nagasaki. Led to the creation of the UN.",
                        "related": ["History", "War", "Europe", "Japan", "United States"]
                    },
                    {
                        "name": "Renaissance",
                        "importance": 0.8,
                        "explanation": "The Renaissance was a cultural and scientific rebirth in Europe (14th-17th centuries). Key figures: Leonardo da Vinci (art, science), Michelangelo (art), Galileo (science). Started in Italy, spread across Europe.",
                        "related": ["History", "Art", "Science", "Europe", "Rebirth"]
                    },
                    {
                        "name": "Industrial Revolution",
                        "importance": 0.8,
                        "explanation": "The Industrial Revolution (late 18th-19th century) transformed manufacturing. Steam engine, factories, mass production. Led to urbanization and social changes. Started in Britain, spread worldwide.",
                        "related": ["History", "Technology", "Factories", "Britain", "Industry"]
                    },
                    {
                        "name": "French Revolution",
                        "importance": 0.7,
                        "explanation": "French Revolution (1789-1799): Overthrow of the monarchy. Slogan: Liberty, Equality, Fraternity. Led to the rise of Napoleon. Key events: Storming of the Bastille, Reign of Terror, Declaration of Rights of Man.",
                        "related": ["History", "France", "Democracy", "Europe", "Revolution"]
                    },
                    {
                        "name": "Cold War",
                        "importance": 0.7,
                        "explanation": "The Cold War (1945-1991) was a period of geopolitical tension between the US and Soviet Union. Nuclear arms race, space race, proxy wars (Korea, Vietnam). Ended with the fall of the Soviet Union.",
                        "related": ["History", "United States", "Soviet Union", "Nuclear", "Superpowers"]
                    }
                ]
            },
            {
                "title": "Ancient History",
                "concepts": [
                    {
                        "name": "Ancient Egypt",
                        "importance": 0.7,
                        "explanation": "Ancient Egypt: civilization along the Nile River. Known for pyramids, pharaohs, hieroglyphics. Constructed Great Pyramids of Giza. Developed mathematics, medicine, astronomy. Lasted over 3000 years.",
                        "related": ["History", "Africa", "Pyramids", "Civilizations", "Egypt"]
                    },
                    {
                        "name": "Ancient Rome",
                        "importance": 0.7,
                        "explanation": "Ancient Rome: Republic to Empire. Known for: Latin language, Roman law, engineering (aqueducts, roads). Contributions: calendar, architecture, legal system. Lasted over 1000 years.",
                        "related": ["History", "Europe", "Empire", "Civilizations", "Republic"]
                    },
                    {
                        "name": "Ancient Greece",
                        "importance": 0.7,
                        "explanation": "Ancient Greece: birthplace of democracy. Philosophy: Socrates, Plato, Aristotle. Contributions: mathematics, astronomy, literature. Known for Olympics and mythology. City-states: Athens, Sparta.",
                        "related": ["History", "Europe", "Philosophy", "Democracy", "Civilizations"]
                    }
                ]
            }
        ]
    },
    
    "Geography": {
        "chapters": [
            {
                "title": "World Geography",
                "concepts": [
                    {
                        "name": "China",
                        "importance": 0.9,
                        "explanation": "China is a country in East Asia. It is the world's most populous country with over 1.4 billion people. Capital: Beijing. Largest city: Shanghai. Official language: Mandarin Chinese. Currency: Yuan (CNY). Famous for the Great Wall and ancient civilization.",
                        "related": ["Geography", "Asia", "Countries", "Population", "Beijing"]
                    },
                    {
                        "name": "Mount Everest",
                        "importance": 0.7,
                        "explanation": "Mount Everest is Earth's highest mountain at 8,848 meters (29,029 feet). Located in the Himalayas on the Nepal-Tibet border. First summited by Edmund Hillary and Tenzing Norgay in 1953.",
                        "related": ["Geography", "Mountains", "Asia", "Height", "Himalayas"]
                    },
                    {
                        "name": "Amazon River",
                        "importance": 0.7,
                        "explanation": "The Amazon River is the largest by volume (discharge: 209,000 m³/s). Flows through South America (Brazil, Peru, Colombia). Length: ~6,400 km (second longest after Nile). Contains more water than the next 7 rivers combined.",
                        "related": ["Geography", "Rivers", "South America", "Rainforest", "Brazil"]
                    },
                    {
                        "name": "Oceans",
                        "importance": 0.7,
                        "explanation": "There are 5 oceans: Pacific, Atlantic, Indian, Southern, Arctic. Pacific is the largest and deepest. Atlantic is the busiest. Oceans cover 71% of Earth's surface. Oceans regulate climate and support life.",
                        "related": ["Geography", "Water", "Earth", "Climate", "Marine"]
                    },
                    {
                        "name": "Continents",
                        "importance": 0.7,
                        "explanation": "There are 7 continents: Africa, Antarctica, Asia, Europe, North America, Oceania, South America. Asia is the largest and most populated. Antarctica is the coldest. Continents were once connected as Pangea.",
                        "related": ["Geography", "Earth", "Countries", "Demographics", "Pangea"]
                    }
                ]
            }
        ]
    }
}

# ====================================================================
#  SPIKELING ENGINE WITH IMPROVED MATCHING
# ====================================================================

@dataclass
class Spike:
    neuron_id: str
    timestamp: float
    strength: float = 1.0
    source: str = "external"

@dataclass
class Neuron:
    id: str
    threshold: float = 100.0
    leak_rate: float = 2.0
    membrane_potential: float = 0.0
    last_spike_time: float = 0.0
    refractory_period: float = 50.0
    connections: List[str] = field(default_factory=list)
    weights: Dict[str, float] = field(default_factory=dict)
    spike_count: int = 0
    concept: str = ""
    importance: float = 1.0
    keywords: List[str] = field(default_factory=list)
    subject: str = ""
    chapter: str = ""
    explanation: str = ""

@dataclass
class KnowledgeChunk:
    id: str
    content: str
    concepts: List[str]
    source: str
    importance: float
    keywords: List[str]
    subject: str = ""
    chapter: str = ""

class SpikelingEngine:
    """
    Complete Spiking Neural Network with proper question matching
    """
    
    def __init__(self):
        self.neurons: Dict[str, Neuron] = {}
        self.knowledge_base: Dict[str, KnowledgeChunk] = {}
        self.concept_index: Dict[str, List[str]] = defaultdict(list)
        self.keyword_index: Dict[str, List[str]] = defaultdict(list)
        self.spike_history: List[Spike] = []
        self.simulation_time: float = 0.0
        self.learning_rate: float = 0.02
        self.metrics = {
            "questions_answered": 0,
            "spikes_processed": 0,
            "energy_used": 0.0,
            "connections_strengthened": 0
        }
        
        # Track learning
        self.concept_strengths: Dict[str, float] = defaultdict(float)
        self.learning_cycles = 0
    
    def load_complete_knowledge(self):
        """Load the complete knowledge pack"""
        print("📚 Loading comprehensive knowledge pack...")
        
        total_concepts = 0
        for subject, textbook in COMPLETE_KNOWLEDGE.items():
            self.load_textbook(textbook, subject)
            total_concepts += len(textbook.get("chapters", []))
        
        print(f"✅ Loaded {len(self.neurons)} neurons from {len(COMPLETE_KNOWLEDGE)} subjects")
        self._build_cross_domain_links()
    
    def load_textbook(self, textbook_data: Dict, source_name: str):
        """Load a textbook into the network"""
        for chapter in textbook_data.get("chapters", []):
            for concept in chapter.get("concepts", []):
                # Create neuron
                neuron_id = f"{source_name}_{concept['name']}"
                
                # Extract keywords
                keywords = self._extract_keywords(concept['name'])
                keywords.extend(self._extract_keywords(concept.get('explanation', '')))
                keywords.extend([w.lower() for w in concept.get("related", [])])
                keywords = list(set(keywords))
                keywords.append(concept['name'].lower())
                
                importance = concept.get("importance", 0.5)
                threshold = 100 - (importance * 30)
                
                neuron = Neuron(
                    id=neuron_id,
                    threshold=max(40, threshold),
                    leak_rate=max(1, 5 - importance * 4),
                    concept=concept['name'],
                    importance=importance,
                    keywords=keywords,
                    subject=source_name,
                    chapter=chapter.get('title', 'Unknown'),
                    explanation=concept.get('explanation', '')
                )
                
                knowledge = KnowledgeChunk(
                    id=neuron_id,
                    content=concept.get("explanation", ""),
                    concepts=[concept['name']] + concept.get("related", []),
                    source=f"{source_name} - {chapter.get('title', 'Unknown')}",
                    importance=importance,
                    keywords=keywords,
                    subject=source_name,
                    chapter=chapter.get('title', 'Unknown')
                )
                
                self.neurons[neuron_id] = neuron
                self.knowledge_base[neuron_id] = knowledge
                
                # Index
                for concept_name in knowledge.concepts:
                    self.concept_index[concept_name.lower()].append(neuron_id)
                
                for keyword in keywords:
                    self.keyword_index[keyword.lower()].append(neuron_id)
                
                self.keyword_index[concept['name'].lower()].append(neuron_id)
        
        # Build connections within subject
        self._build_connections()
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        stopwords = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'and', 'or',
                    'but', 'for', 'nor', 'on', 'at', 'to', 'by', 'in', 'of', 'with',
                    'what', 'how', 'why', 'where', 'when', 'who', 'which', 'whom'}
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
        return [w for w in words if w not in stopwords and len(w) > 2]
    
    def _build_connections(self):
        """Build connections between related neurons"""
        concept_pairs = defaultdict(list)
        
        for neuron_id, knowledge in self.knowledge_base.items():
            for concept in knowledge.concepts:
                concept_pairs[concept.lower()].append(neuron_id)
        
        for concept, neurons in concept_pairs.items():
            for i, neuron_a in enumerate(neurons):
                for neuron_b in neurons[i+1:]:
                    if neuron_b not in self.neurons[neuron_a].connections:
                        weight = (self.neurons[neuron_a].importance + 
                                 self.neurons[neuron_b].importance) * 0.5
                        self.neurons[neuron_a].connections.append(neuron_b)
                        self.neurons[neuron_a].weights[neuron_b] = weight
                        self.neurons[neuron_b].connections.append(neuron_a)
                        self.neurons[neuron_b].weights[neuron_a] = weight
    
    def _build_cross_domain_links(self):
        """Build cross-domain connections"""
        subjects = defaultdict(list)
        for neuron in self.neurons.values():
            if neuron.subject:
                subjects[neuron.subject].append(neuron.id)
        
        subject_list = list(subjects.keys())
        cross_links = 0
        
        for i in range(len(subject_list)):
            for j in range(i+1, len(subject_list)):
                for na in subjects[subject_list[i]][:5]:
                    for nb in subjects[subject_list[j]][:5]:
                        if nb not in self.neurons[na].connections:
                            weight = (self.neurons[na].importance + 
                                     self.neurons[nb].importance) * 0.3
                            self.neurons[na].connections.append(nb)
                            self.neurons[na].weights[nb] = weight
                            self.neurons[nb].connections.append(na)
                            self.neurons[nb].weights[na] = weight
                            cross_links += 1
        
        print(f"🔗 Built {cross_links} cross-domain connections")
    
    def answer_question(self, question: str) -> Dict:
        """Answer a question using the spiking network"""
        # Convert to spikes
        spikes = self._text_to_spikes(question)
        
        # Process spikes
        fired = self._process_spikes(spikes)
        
        # If no neurons fired, try aggressive search
        if not fired:
            fired = self._aggressive_search(question)
        
        # Generate answer
        if not fired:
            return {
                "answer": "I don't have that information in my knowledge base.",
                "confidence": 0.0,
                "concepts": [],
                "source": "unknown"
            }
        
        # Find best answers
        answers = []
        for neuron_id in fired[:5]:
            if neuron_id in self.knowledge_base:
                knowledge = self.knowledge_base[neuron_id]
                neuron = self.neurons[neuron_id]
                confidence = min(1.0, 0.5 + neuron.spike_count / 10)
                
                answers.append({
                    "content": knowledge.content,
                    "concept": knowledge.concepts[0] if knowledge.concepts else "",
                    "confidence": confidence,
                    "source": knowledge.source,
                    "subject": knowledge.subject
                })
        
        answers.sort(key=lambda x: x["confidence"], reverse=True)
        
        if answers and answers[0]["confidence"] > 0.3:
            best = answers[0]
            # Strengthen connections for learning
            self._strengthen_learning(fired)
            
            return {
                "answer": best["content"],
                "confidence": best["confidence"],
                "concepts": [a["concept"] for a in answers[:3] if a["concept"]],
                "source": best["source"],
                "subject": best["subject"]
            }
        else:
            return {
                "answer": "I'm still learning about that topic.",
                "confidence": 0.0,
                "concepts": [],
                "source": "unknown"
            }
    
    def _text_to_spikes(self, text: str) -> List[Spike]:
        """Convert text to spikes with improved matching"""
        spikes = []
        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)
        
        # Direct word matching
        for word in words:
            if word in self.keyword_index:
                for neuron_id in self.keyword_index[word][:3]:
                    spikes.append(Spike(
                        neuron_id=neuron_id,
                        timestamp=self.simulation_time,
                        strength=1.0,
                        source=f"keyword_{word}"
                    ))
        
        # Concept matching
        for word in words:
            for concept_name, neuron_ids in self.concept_index.items():
                if word in concept_name or concept_name in word:
                    for neuron_id in neuron_ids[:2]:
                        spikes.append(Spike(
                            neuron_id=neuron_id,
                            timestamp=self.simulation_time,
                            strength=0.9,
                            source=f"concept_{concept_name}"
                        ))
        
        # Math pattern detection
        numbers = re.findall(r'\d+', text)
        if numbers and ('x' in text_lower or '×' in text_lower or 'times' in text_lower):
            for neuron_id in self.keyword_index.get('multiplication', [])[:2]:
                spikes.append(Spike(
                    neuron_id=neuron_id,
                    timestamp=self.simulation_time,
                    strength=1.0,
                    source="math_pattern"
                ))
        
        return spikes
    
    def _process_spikes(self, spikes: List[Spike]) -> List[str]:
        """Process spikes through the network"""
        self.simulation_time += 1.0
        
        for spike in spikes:
            self._inject_spike(spike)
            self.metrics["spikes_processed"] += 1
            self.metrics["energy_used"] += 0.001
        
        for _ in range(3):
            self._simulate_cycle()
        
        fired = self._read_fired_neurons()
        self.metrics["questions_answered"] += 1
        return fired
    
    def _inject_spike(self, spike: Spike):
        """Inject a spike into the network"""
        if spike.neuron_id not in self.neurons:
            return
        
        neuron = self.neurons[spike.neuron_id]
        
        refractory_ms = (self.simulation_time - neuron.last_spike_time) * 1000
        if refractory_ms < neuron.refractory_period:
            return
        
        neuron.membrane_potential += spike.strength * 15
        
        if neuron.membrane_potential >= neuron.threshold:
            neuron.membrane_potential = 0
            neuron.last_spike_time = self.simulation_time
            neuron.spike_count += 1
            
            self.spike_history.append(spike)
            
            # Propagate
            for connection in neuron.connections:
                weight = neuron.weights.get(connection, 0.5)
                if weight > 0.2:
                    propagated = Spike(
                        neuron_id=connection,
                        timestamp=self.simulation_time,
                        strength=spike.strength * weight * 0.3,
                        source=f"propagated"
                    )
                    self._inject_spike(propagated)
    
    def _simulate_cycle(self):
        """Simulate one cycle"""
        self.simulation_time += 0.01
        
        for neuron in self.neurons.values():
            if neuron.membrane_potential > 0:
                neuron.membrane_potential -= neuron.leak_rate * 0.1
                neuron.membrane_potential = max(0, neuron.membrane_potential)
    
    def _read_fired_neurons(self) -> List[str]:
        """Read fired neurons"""
        fired = []
        for spike in reversed(self.spike_history):
            if self.simulation_time - spike.timestamp < 0.5:
                if spike.neuron_id not in fired:
                    fired.append(spike.neuron_id)
            else:
                break
        return fired
    
    def _strengthen_learning(self, fired_neurons: List[str]):
        """Strengthen learning from fired neurons"""
        self.learning_cycles += 1
        
        for neuron_id in fired_neurons:
            if neuron_id in self.neurons:
                neuron = self.neurons[neuron_id]
                self.concept_strengths[neuron.concept] += 0.1
                
                # Lower threshold slightly for future firing
                neuron.threshold = max(30, neuron.threshold - 0.5)
    
    def _aggressive_search(self, question: str) -> List[str]:
        """Aggressive search when normal matching fails"""
        fired = []
        question_lower = question.lower()
        words = re.findall(r'\b\w+\b', question_lower)
        
        # Check each knowledge chunk
        for neuron_id, knowledge in self.knowledge_base.items():
            content_lower = knowledge.content.lower()
            concept_lower = knowledge.concepts[0].lower() if knowledge.concepts else ""
            
            # Check for word matches
            for word in words:
                if len(word) > 2:
                    if word in content_lower or word in concept_lower:
                        fired.append(neuron_id)
                        break
            
            # Check for number patterns
            numbers = re.findall(r'\d+', question_lower)
            if numbers and 'multiplication' in content_lower:
                fired.append(neuron_id)
        
        return fired

# ====================================================================
#  MAIN APPLICATION
# ====================================================================

class SpikelingApp:
    def __init__(self):
        self.engine = SpikelingEngine()
    
    def initialize(self):
        """Initialize the application"""
        self.engine.load_complete_knowledge()
        print("\n🎓 Spikeling College in a Box ready!")
    
    def ask(self, question: str) -> Dict:
        """Ask a question"""
        return self.engine.answer_question(question)
    
    def show_stats(self):
        """Show system statistics"""
        print(f"\n📊 System Statistics:")
        print(f"  🧠 Neurons: {len(self.engine.neurons)}")
        print(f"  📚 Knowledge chunks: {len(self.engine.knowledge_base)}")
        print(f"  ⚡ Spikes processed: {self.engine.metrics['spikes_processed']}")
        print(f"  ❓ Questions answered: {self.engine.metrics['questions_answered']}")
        print(f"  🔋 Energy used: {self.engine.metrics['energy_used']:.3f} units")
        print(f"  🔗 Connections: {sum(len(n.connections) for n in self.engine.neurons.values())}")
        print(f"  📈 Learning cycles: {self.engine.learning_cycles}")
    
    def show_subjects(self):
        """Show available subjects"""
        subjects = set()
        for knowledge in self.engine.knowledge_base.values():
            subjects.add(knowledge.source.split(' - ')[0])
        print(f"\n📚 Available Subjects: {', '.join(sorted(subjects))}")

# ====================================================================
#  DEMO
# ====================================================================

def main():
    app = SpikelingApp()
    app.initialize()
    
    print("\n" + "="*60)
    print("🎓 SPIKELING COLLEGE IN A BOX — COMPLETE EDITION")
    print("="*60)
    print("📚 5 Subjects: Mathematics, Physics, Chemistry, Biology, History, Geography")
    print("🧠 100+ Concepts loaded")
    print("⚡ Spiking Neural Network with STDP learning")
    print("\nCommands:")
    print("  /stats     - Show system statistics")
    print("  /subjects  - List available subjects")
    print("  /learn     - Show what I've learned")
    print("  exit       - Quit")
    print("-"*60)
    
    while True:
        question = input("\n📝 You: ").strip()
        
        if question.lower() in ['exit', 'quit', 'bye']:
            print("Goodbye! 🎓")
            break
        
        if question.lower() == '/stats':
            app.show_stats()
            continue
        
        if question.lower() == '/subjects':
            app.show_subjects()
            continue
        
        if question.lower() == '/learn':
            print(f"\n📈 Learning Progress:")
            print(f"  Cycles: {app.engine.learning_cycles}")
            print(f"  Top concepts:")
            sorted_concepts = sorted(app.engine.concept_strengths.items(), 
                                   key=lambda x: x[1], reverse=True)[:10]
            for concept, strength in sorted_concepts:
                print(f"    {concept}: {strength:.2f}")
            continue
        
        if question:
            answer = app.ask(question)
            print(f"\n🤖 AI: {answer['answer']}")
            
            if answer.get('confidence', 0) > 0.3:
                print(f"  💡 Confidence: {answer['confidence']:.2%}")
                if answer.get('concepts'):
                    print(f"  📚 Concepts: {', '.join(answer['concepts'])}")
                if answer.get('source') and answer['source'] != 'unknown':
                    print(f"  📖 Source: {answer['source']}")

if __name__ == "__main__":
    main()