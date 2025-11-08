using System;
using System.IO;
using System.Diagnostics;
using System.Collections.Generic;
using System.Threading;
using System.Reflection;

namespace SmartestSearchWatcher
{
    class Program
    {
        // Directories to skip (same as Python config)
        private static readonly HashSet<string> SKIP_FOLDERS = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "windows", "program files", "program files (x86)", "programdata",
            "$recycle.bin", "system volume information", "temp", "tmp",
            "appdata", "node_modules", "__pycache__", ".git", ".vscode"
        };

        private static readonly HashSet<string> SKIP_PATTERNS = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "temp", "tmp", "cache", "__pycache__", "node_modules", "pkg", ".vscode"
        };

        // Get Python script path from same directory as executable
        private static string GetPythonScriptPath()
        {
            // The auto_index.py script should be in the same folder as this executable
            string exeDir = AppContext.BaseDirectory;
            return Path.Combine(exeDir, "auto_index.py");
        }

        static void Main(string[] args)
        {
            Console.WriteLine("Smartest Search - File Watcher Started");
            Console.WriteLine("Watching for new files...\n");

            // Verify Python script exists
            string pythonScript = GetPythonScriptPath();
            if (!File.Exists(pythonScript))
            {
                Console.WriteLine($"ERROR: auto_index.py not found at: {pythonScript}");
                Console.WriteLine("Press any key to exit...");
                Console.ReadKey();
                return;
            }
            Console.WriteLine($"Using Python script: {pythonScript}\n");

            // Get all available drives
            DriveInfo[] drives = DriveInfo.GetDrives();
            List<FileSystemWatcher> watchers = new List<FileSystemWatcher>();

            foreach (var drive in drives)
            {
                if (drive.IsReady && drive.DriveType == DriveType.Fixed)
                {
                    try
                    {
                        var watcher = CreateWatcher(drive.Name);
                        watchers.Add(watcher);
                        Console.WriteLine($"Watching drive: {drive.Name}");
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"Could not watch {drive.Name}: {ex.Message}");
                    }
                }
            }

            Console.WriteLine("\nFile watcher active. Press Ctrl+C to stop.");
            
            // Keep application running
            Thread.Sleep(Timeout.Infinite);
        }

        private static FileSystemWatcher CreateWatcher(string path)
        {
            var watcher = new FileSystemWatcher
            {
                Path = path,
                IncludeSubdirectories = true,
                NotifyFilter = NotifyFilters.FileName | NotifyFilters.DirectoryName | NotifyFilters.CreationTime,
                Filter = "*.*"
            };

            // Subscribe to Created event
            watcher.Created += OnFileCreated;

            // Start watching
            watcher.EnableRaisingEvents = true;

            return watcher;
        }

        private static void OnFileCreated(object sender, FileSystemEventArgs e)
        {
            try
            {
                // Skip if path contains excluded patterns
                if (ShouldSkipPath(e.FullPath))
                {
                    return;
                }

                // Give the file a moment to finish being created
                Thread.Sleep(100);

                // Call Python auto_index script asynchronously
                CallAutoIndex(e.FullPath);
            }
            catch (Exception ex)
            {
                // Silently ignore errors (don't spam console)
                Console.WriteLine($"Error processing {e.Name}: {ex.Message}");
            }
        }

        private static bool ShouldSkipPath(string path)
        {
            string lowerPath = path.ToLower();

            // Check skip folders
            foreach (var folder in SKIP_FOLDERS)
            {
                if (lowerPath.Contains($"\\{folder}\\") || lowerPath.EndsWith($"\\{folder}"))
                {
                    return true;
                }
            }

            // Check skip patterns
            foreach (var pattern in SKIP_PATTERNS)
            {
                if (lowerPath.Contains(pattern))
                {
                    return true;
                }
            }

            return false;
        }

        private static void CallAutoIndex(string filePath)
        {
            try
            {
                // Get Python script path (should be in same directory as this exe)
                string pythonScript = GetPythonScriptPath();
                
                if (!File.Exists(pythonScript))
                {
                    Console.WriteLine($"ERROR: auto_index.py not found at {pythonScript}");
                    return;
                }
                
                // Create process to run Python script (do not redirect output to avoid blocking)
                var processInfo = new ProcessStartInfo
                {
                    FileName = "python",
                    Arguments = $"\"{pythonScript}\" \"{filePath}\"",
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = false,
                    RedirectStandardError = false
                };

                try
                {
                    Process.Start(processInfo);
                    Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] Indexed: {Path.GetFileName(filePath)}");
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Failed to start python for {filePath}: {ex.Message}");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error calling auto_index: {ex.Message}");
            }
        }
    }
}