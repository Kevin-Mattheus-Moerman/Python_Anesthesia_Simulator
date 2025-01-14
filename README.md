[![status](https://joss.theoj.org/papers/61d34ad9ef855a128509b4279e2c9325/status.svg)](https://joss.theoj.org/papers/61d34ad9ef855a128509b4279e2c9325)

# Python_Anesthesia_Simulator
The Python Anesthesia Simulator (PAS) models the effect of drugs on physiological variables during total intravenous anesthesia. It is particularly dedicated to the control community, to be used as a benchmark for the design of multidrug controllers. The available drugs are Propofol, Remifentanil, and Norepinephrine, the outputs are the Bispectral index (BIS), Mean Arterial Pressure (MAP), Cardiac Output (CO), and Tolerance of Laryngoscopy (TOL). PAS includes different well-known models along with their uncertainties to simulate inter-patient variability. Blood loss can also be simulated to assess the controller's performance in a shock scenario. Finally, PAS includes standard disturbance profiles and metrics computation to facilitate the evaluation of the controller's performances.

## Structure

    .
    ├─── src
    |   ├─── python_anesthesia_simulator           # Simulator library + metrics function
    |
    ├── example            # example of controller test pipeline with the library 
    ├── ...
    ├── paper              # markdown paper for JOSS submition
    ├── ...
    ├── tests              # file for testing the package
    ├── ...
    ├── LICENSE
    ├── pyproject.toml      # packaging file
    ├── requirements.txt
    ├── README.md
    └── .gitignore          

## Installation
Download the git repository and use pip to install the package:
```python
    git clone https://github.com/BobAubouin/Python_Anesthesia_Simulator.git
    pip install .\Python_Anesthesia_Simulator
```
The package can be imported in your python script with:
```python
    import python_anesthesia_simulator as pas
```

## Documentation
Available in the _Documentation.pdf_ file.

## License

_GNU General Public License 3.0_

## Project status
Submitted to JOSS

## Author
Bob Aubouin--Paitault
