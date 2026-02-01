try:
    from .visualizer import main
except ImportError:
    from audio_visualizer.visualizer import main

if __name__ == "__main__":
    main()
