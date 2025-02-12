
import { useState, useEffect } from "react";
import { createClient } from "@supabase/supabase-js";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "@/components/ui/use-toast";
import { Loader2, Key } from "lucide-react";

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
);

const Profile = () => {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [githubToken, setGithubToken] = useState("");

  useEffect(() => {
    const getUser = async () => {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        setUser(user);
        
        // Fetch existing token if any
        if (user) {
          const { data, error } = await supabase
            .from('github_tokens')
            .select('token')
            .eq('user_id', user.id)
            .single();
            
          if (data?.token) {
            setGithubToken(data.token);
          }
        }
      } catch (error) {
        console.error("Error fetching user:", error);
        toast({
          title: "Error",
          description: "Failed to load user profile",
          variant: "destructive",
        });
      } finally {
        setLoading(false);
      }
    };

    getUser();
  }, []);

  const handleTokenUpdate = async () => {
    if (!user) return;

    try {
      const { error } = await supabase
        .from('github_tokens')
        .upsert({ 
          user_id: user.id,
          token: githubToken,
          updated_at: new Date().toISOString()
        });

      if (error) throw error;

      toast({
        title: "Success",
        description: "GitHub token updated successfully",
      });
    } catch (error) {
      console.error("Error updating token:", error);
      toast({
        title: "Error",
        description: "Failed to update GitHub token",
        variant: "destructive",
      });
    }
  };

  const handleSignOut = async () => {
    try {
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
      window.location.href = "/";
    } catch (error) {
      console.error("Error signing out:", error);
      toast({
        title: "Error",
        description: "Failed to sign out",
        variant: "destructive",
      });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="animate-spin" />
      </div>
    );
  }

  if (!user) {
    window.location.href = "/";
    return null;
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="container py-12 max-w-2xl">
        <h1 className="text-4xl font-bold text-github-gray mb-8">Profile</h1>
        
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <div className="flex items-center gap-4 mb-6">
            <img 
              src={user.user_metadata.avatar_url} 
              alt="Profile" 
              className="w-16 h-16 rounded-full"
            />
            <div>
              <h2 className="text-xl font-semibold">{user.user_metadata.full_name}</h2>
              <p className="text-gray-600">{user.email}</p>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <Key className="w-5 h-5" />
            GitHub Token Management
          </h3>
          
          <div className="space-y-4">
            <div>
              <Input
                type="password"
                value={githubToken}
                onChange={(e) => setGithubToken(e.target.value)}
                placeholder="Enter your GitHub token"
                className="mb-2"
              />
              <p className="text-sm text-gray-600 mb-4">
                This token will be used to create repositories in the Rastion organization.
              </p>
            </div>
            
            <div className="flex gap-4">
              <Button onClick={handleTokenUpdate}>
                Update Token
              </Button>
              <Button 
                variant="outline" 
                onClick={() => window.open("https://github.com/settings/tokens/new", "_blank")}
              >
                Generate New Token
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-8">
          <Button variant="outline" onClick={handleSignOut}>
            Sign Out
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Profile;
