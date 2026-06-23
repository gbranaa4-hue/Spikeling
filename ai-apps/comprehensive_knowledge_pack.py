# comprehensive_knowledge_pack.py
"""
Complete educational knowledge base for Spikeling AI
Covers: Math, Physics, Chemistry, Biology, History, Geography
"""

COMPREHENSIVE_KNOWLEDGE = {
    "Mathematics": {
        "chapters": [
            {
                "title": "Basic Arithmetic",
                "concepts": [
                    {
                        "name": "Addition",
                        "importance": 1.0,
                        "explanation": "Addition is combining numbers to find their total. 4 + 2 = 6. 10 + 5 = 15. Addition is one of the four basic operations of arithmetic.",
                        "related": ["Math", "Numbers", "Operations", "Subtraction"]
                    },
                    {
                        "name": "Subtraction",
                        "importance": 0.9,
                        "explanation": "Subtraction is taking one number away from another. 5 - 3 = 2. 10 - 4 = 6. The result is called the difference.",
                        "related": ["Math", "Numbers", "Operations", "Addition"]
                    },
                    {
                        "name": "Multiplication",
                        "importance": 0.9,
                        "explanation": "Multiplication is repeated addition. 3 × 4 = 12 means 3 added 4 times. 7 × 8 = 56. It's a faster way to add equal groups.",
                        "related": ["Math", "Numbers", "Operations", "Division"]
                    },
                    {
                        "name": "Division",
                        "importance": 0.8,
                        "explanation": "Division is splitting into equal parts. 12 ÷ 3 = 4 means 12 split into 3 equal groups of 4. 20 ÷ 5 = 4.",
                        "related": ["Math", "Numbers", "Operations", "Multiplication"]
                    }
                ]
            },
            {
                "title": "Algebra",
                "concepts": [
                    {
                        "name": "Algebra",
                        "importance": 0.8,
                        "explanation": "Algebra uses letters (variables) to represent numbers in equations. For example, x + 3 = 7, so x = 4. It's the foundation for higher mathematics.",
                        "related": ["Math", "Equations", "Variables", "Calculus"]
                    },
                    {
                        "name": "Equation",
                        "importance": 0.8,
                        "explanation": "An equation shows that two expressions are equal, using an equals sign (=). Example: 2x + 3 = 11. Solving means finding the value of x.",
                        "related": ["Math", "Algebra", "Variables"]
                    },
                    {
                        "name": "Derivative",
                        "importance": 0.7,
                        "explanation": "A derivative measures how a function changes as its input changes. The derivative of x² is 2x. It's used to find rates of change and slopes of curves.",
                        "related": ["Math", "Calculus", "Rates", "Physics"]
                    }
                ]
            },
            {
                "title": "Geometry",
                "concepts": [
                    {
                        "name": "Geometry",
                        "importance": 0.8,
                        "explanation": "Geometry is the study of shapes, sizes, and positions of figures. It includes points, lines, angles, and surfaces.",
                        "related": ["Math", "Shapes", "Angles", "Measurement"]
                    },
                    {
                        "name": "Pythagorean Theorem",
                        "importance": 0.8,
                        "explanation": "In a right triangle, a² + b² = c² where c is the hypotenuse. For a 3-4-5 triangle: 3² + 4² = 5² (9+16=25). Discovered by Pythagoras.",
                        "related": ["Math", "Geometry", "Triangles", "Measurement"]
                    }
                ]
            }
        ]
    },
    
    "Physics": {
        "chapters": [
            {
                "title": "Classical Mechanics",
                "concepts": [
                    {
                        "name": "Gravity",
                        "importance": 1.0,
                        "explanation": "Gravity is a force that attracts objects with mass toward each other. On Earth, it gives weight to objects and pulls everything toward the center. The acceleration due to gravity is 9.8 m/s². Newton's Law of Universal Gravitation states every mass attracts every other mass with a force proportional to the product of their masses and inversely proportional to the square of the distance between them.",
                        "related": ["Physics", "Force", "Mass", "Newton", "Acceleration"]
                    },
                    {
                        "name": "Force",
                        "importance": 0.9,
                        "explanation": "A force is a push or pull on an object. It causes acceleration. Force = mass × acceleration (F=ma). Measured in Newtons (N). Forces include gravity, friction, and magnetism.",
                        "related": ["Physics", "Motion", "Newton", "Mass"]
                    },
                    {
                        "name": "Newton's Laws",
                        "importance": 0.9,
                        "explanation": "1st Law: Objects at rest stay at rest, moving objects stay moving (inertia). 2nd Law: Force = mass × acceleration (F=ma). 3rd Law: For every action, there's an equal and opposite reaction.",
                        "related": ["Physics", "Force", "Motion", "Inertia"]
                    },
                    {
                        "name": "Energy",
                        "importance": 0.8,
                        "explanation": "Energy is the ability to do work. It comes in forms: kinetic (energy of motion), potential (stored energy), thermal (heat), chemical, and more. Energy cannot be created or destroyed, only transformed.",
                        "related": ["Physics", "Work", "Power", "Thermodynamics"]
                    },
                    {
                        "name": "Motion",
                        "importance": 0.8,
                        "explanation": "Motion is the change in position of an object over time. Described by velocity (speed with direction) and acceleration (rate of change of velocity). Speed = distance / time.",
                        "related": ["Physics", "Velocity", "Acceleration", "Speed"]
                    },
                    {
                        "name": "Mass",
                        "importance": 0.8,
                        "explanation": "Mass is the amount of matter in an object. It's measured in kilograms (kg). It's different from weight, which is the force of gravity on mass. Mass resists change in motion (inertia).",
                        "related": ["Physics", "Weight", "Gravity", "Inertia"]
                    }
                ]
            },
            {
                "title": "Modern Physics",
                "concepts": [
                    {
                        "name": "Einstein",
                        "importance": 0.7,
                        "explanation": "Albert Einstein developed the theory of relativity. E=mc² means energy equals mass times the speed of light squared. This shows mass and energy are equivalent.",
                        "related": ["Physics", "Relativity", "Energy", "Speed of Light"]
                    },
                    {
                        "name": "Quantum Mechanics",
                        "importance": 0.7,
                        "explanation": "Quantum mechanics describes physics at atomic and subatomic scales. Particles can behave as both waves and particles. Key concepts: uncertainty principle, superposition, and wave functions.",
                        "related": ["Physics", "Atoms", "Particles", "Waves"]
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
                        "name": "Water",
                        "importance": 0.9,
                        "explanation": "Water (H₂O) is a molecule made of two hydrogen atoms and one oxygen atom. It's essential for all known life. It's a polar molecule, universal solvent, and has unique properties like surface tension and high specific heat.",
                        "related": ["Chemistry", "Molecules", "Hydrogen", "Oxygen", "Biology"]
                    },
                    {
                        "name": "Atom",
                        "importance": 0.9,
                        "explanation": "An atom is the basic unit of matter. It has a nucleus containing protons and neutrons, surrounded by electrons. Atoms combine to form molecules.",
                        "related": ["Chemistry", "Molecules", "Protons", "Neutrons", "Electrons"]
                    },
                    {
                        "name": "Molecule",
                        "importance": 0.8,
                        "explanation": "A molecule is two or more atoms bonded together. Examples: H₂O (water), CO₂ (carbon dioxide), O₂ (oxygen gas). Molecules can be elements or compounds.",
                        "related": ["Chemistry", "Atoms", "Bonds", "Compounds"]
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
                        "explanation": "The cell is the basic unit of life. All living things are made of cells. There are two types: prokaryotic (simple, no nucleus) and eukaryotic (complex, with nucleus).",
                        "related": ["Biology", "Life", "DNA", "Organelles"]
                    },
                    {
                        "name": "DNA",
                        "importance": 0.9,
                        "explanation": "DNA (deoxyribonucleic acid) is the molecule that carries genetic information. It has a double helix structure. It contains instructions for building and maintaining an organism.",
                        "related": ["Biology", "Genetics", "Chromosomes", "RNA"]
                    },
                    {
                        "name": "Photosynthesis",
                        "importance": 0.8,
                        "explanation": "Photosynthesis is how plants make food using sunlight, water, and carbon dioxide. 6CO₂ + 6H₂O + light → C₆H₁₂O₆ + 6O₂. It produces oxygen and glucose.",
                        "related": ["Biology", "Plants", "Energy", "Chlorophyll"]
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
                        "importance": 0.8,
                        "explanation": "World War II (1939-1945) was the deadliest conflict in history. Over 70 million people died. It involved the Axis Powers (Germany, Japan, Italy) against the Allies (UK, US, Soviet Union).",
                        "related": ["History", "War", "Europe", "1940s"]
                    },
                    {
                        "name": "Renaissance",
                        "importance": 0.7,
                        "explanation": "The Renaissance was a period of cultural, artistic, and scientific rebirth in Europe (14th-17th centuries). It produced artists like da Vinci and Michelangelo, and scientists like Galileo.",
                        "related": ["History", "Art", "Science", "Europe"]
                    }
                ]
            }
        ]
    },
    
    "Geography": {
        "chapters": [
            {
                "title": "Physical Geography",
                "concepts": [
                    {
                        "name": "Mount Everest",
                        "importance": 0.7,
                        "explanation": "Mount Everest is the highest mountain on Earth at 8,848 meters (29,029 feet). It's in the Himalayan mountain range on the Nepal-Tibet border.",
                        "related": ["Geography", "Mountains", "Asia", "Height"]
                    },
                    {
                        "name": "Amazon River",
                        "importance": 0.6,
                        "explanation": "The Amazon River is the largest river by volume in the world. It flows through South America and contains more water than the next 7 largest rivers combined.",
                        "related": ["Geography", "Rivers", "South America", "Rainforest"]
                    }
                ]
            }
        ]
    }
}

def load_comprehensive_knowledge(engine):
    """
    Load all knowledge into the Spikeling engine
    """
    print("📚 Loading comprehensive knowledge pack...")
    
    for subject, textbook in COMPREHENSIVE_KNOWLEDGE.items():
        engine.load_textbook(textbook, subject)
    
    print(f"✅ Loaded {len(engine.neurons)} knowledge neurons")
    print(f"📚 Subjects covered: {', '.join(COMPREHENSIVE_KNOWLEDGE.keys())}")