from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return """
    <h2>Oops! Site's Down.</h2>
    <p>We're currently working on optimizing the site.</p>
    <p>Basically... it needs some fixing before we're ready to
    put it back online.</p>
    <p>For queries: <a href="mailto:admin@firewave.in">admin@firewave.in</a></p>
    """

if __name__ == "__main__":
    app.run()
