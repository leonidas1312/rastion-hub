import { Code2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import CodeBlock from "@/components/CodeBlock";  // Import the CodeBlock component

// Dummy dropdown options – you can expand these as needed.
const problemOptions = [
  { label: "Rastion/max-cut", value: "max-cut" },
  { label: "Rastion/portfolio-optimization", value: "portfolio-optimization" },
  // Add more problems here.
];

const optimizerOptions = [
  { label: "Rastion/exhaustive-search", value: "exhaustive-search" },
  { label: "Rastion/particle-swarm", value: "particle-swarm" },
  // Add more optimizers here.
];

const ExecutableCodeBox = ({ codeSnippet }) => {
  const [output, setOutput] = useState("");
  const [loading, setLoading] = useState(false);

  const runCode = async () => {
    setLoading(true);
    setOutput(""); // Clear previous output

    try {
      const response = await fetch("/.netlify/functions/run-code", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: codeSnippet }),
      });

      if (!response.body) {
        throw new Error("ReadableStream not supported in this browser/environment.");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      // Read the stream chunk by chunk.
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        setOutput((prev) => prev + decoder.decode(value));
      }
    } catch (error: any) {
      setOutput("Error: " + error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative">
      {/* Render the code snippet with CodeBlock (non-executable display) */}
      <CodeBlock code={codeSnippet} language="python" />

      <Button onClick={runCode} className="mt-2" disabled={loading}>
        {loading ? "Running..." : "Run Code"}
      </Button>
      <div className="mt-4 bg-black text-green-400 p-4 rounded font-mono text-sm h-48 overflow-y-auto">
        {output || "Terminal output..."}
      </div>
    </div>
  );
};

const Landing = () => {
  const [user, setUser] = useState(null);
  const [selectedProblem, setSelectedProblem] = useState(problemOptions[0].value);
  const [selectedOptimizer, setSelectedOptimizer] = useState(optimizerOptions[0].value);

  useEffect(() => {
    const getUser = async () => {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      setUser(user);
    };

    getUser();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  // The code snippet – using the selected values dynamically.
  const codeSnippet = `from qubots.auto_problem import AutoProblem
from qubots.auto_optimizer import AutoOptimizer

# Load the max-cut problem from the repository.
problem = AutoProblem.from_repo("Rastion/${selectedProblem}")

# Load the optimizer from the repository.
optimizer = AutoOptimizer.from_repo("Rastion/${selectedOptimizer}")

best_solution, best_cost = optimizer.optimize(problem)
print(180*"=")
print("Solved maxcut using exhaustive search")
print("Best Solution:", best_solution)
print("Best Cost:", best_cost)
print(180*"=")`;

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-12">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold flex items-center justify-center text-github-gray mb-4">
            <div className="text-center">
              <img src="/rastion1.svg" alt="Rastion Logo" className="w-full max-w-[250px]" />
            </div>
          </h1>

          <p className="text-xl text-github-gray mb-8 text-center">
            An open source community for optimization.
            <br />
            <span className="text-xl text-github-gray mb-8 text-center">Currently under development, see Documentation for more info.</span>
          </p>
          

          <div className="flex gap-4 justify-center">
            <Button asChild>
              <Link to="/repositories">Browse Repositories</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/docs">Read Documentation</Link>
            </Button>
          </div>
        </div>

        <div className="max-w text-github-gray">
          <p className="mb-4 text-2xl">
              🚀 Use qubots on the fly!
          </p>
        </div>

        

        {/* Get Started Section */}
        <div className="mb-16">
          <div className="bg-gradient-to-br from-[#1A1F2C] to-[#221F26] p-6 rounded-lg shadow-xl">
            <div className="mb-4 text-white text-xl">
              I want to solve this problem&nbsp;
              <select
                value={selectedProblem}
                onChange={(e) => setSelectedProblem(e.target.value)}
                className="bg-gray-800 text-white px-2 py-1 rounded"
              >
                {problemOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              &nbsp;using this optimizer&nbsp;
              <select
                value={selectedOptimizer}
                onChange={(e) => setSelectedOptimizer(e.target.value)}
                className="bg-gray-800 text-white px-2 py-1 rounded"
              >
                {optimizerOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <ExecutableCodeBox codeSnippet={codeSnippet} />
          </div>
        </div>

      </div>
    </div>

      



  );
};

export default Landing;
