
import { Code2 } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

const Landing = () => {
  return (
    <div className="min-h-screen bg-white">
      <div className="container py-12">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-github-gray mb-4">Rastion-Hub</h1>
          <p className="text-xl text-github-gray mb-8">Optimizing together</p>
          <div className="max-w-2xl mx-auto text-github-gray mb-12">
            <p className="mb-4">
              At RastionHub, we believe in the power of open source to drive
              innovation and optimization. By sharing our tools and knowledge, we
              create a collaborative environment where the optimization community
              can grow and thrive together.
            </p>
            <p>
              Join us in building a more efficient future through open source
              collaboration.
            </p>
          </div>
          <div className="flex gap-4 justify-center">
            <Button asChild>
              <Link to="/repositories">Browse Repositories</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/docs">Read Documentation</Link>
            </Button>
          </div>
        </div>

        <div className="mb-16">
          <h2 className="text-2xl font-semibold text-github-gray mb-6">Get Started with Rastion</h2>
          <div className="grid md:grid-cols-2 gap-8">
            <div className="bg-gray-50 p-6 rounded-lg">
              <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <Code2 className="w-5 h-5" />
                Using Optimizers and Solvers
              </h3>
              <pre className="bg-white p-4 rounded text-sm overflow-x-auto">
{`from rastion_hub.auto_optimizer import AutoOptimizer
from rastion_hub.auto_problem import AutoProblem

# Load a problem from the hub
problem = AutoProblem.from_repo(
    "Rastion/my-problem-repo", 
    revision="main"
)

# Load and run an optimizer
solver = AutoOptimizer.from_repo(
    "Rastion/my-solver-repo", 
    revision="main"
)
solution, value = solver.optimize(problem)`}
              </pre>
            </div>

            <div className="bg-gray-50 p-6 rounded-lg">
              <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
                <Code2 className="w-5 h-5" />
                Sharing Your Work
              </h3>
              <pre className="bg-white p-4 rounded text-sm overflow-x-auto">
{`# Create a new solver repository
rastion create_repo my-solver --org Rastion

# Push your solver code and config
rastion push_solver my-solver \\
    --file my_solver.py \\
    --config solver_config.json

# Create and push a problem
rastion create_repo my-problem --org Rastion
rastion push_problem my-problem \\
    --file my_problem.py \\
    --config problem_config.json`}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Landing;
