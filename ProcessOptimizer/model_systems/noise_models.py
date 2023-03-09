from abc import ABC, abstractmethod
from typing import Optional, Callable

from  scipy.stats import norm

class NoiseModel(ABC):
    """Abstract class that noise models inherit"""
    def __init__(
            self,
            noise_size: float,
            underlying_noise_model: Optional["NoiseModel"] = None,
            noise_dist: Callable[[],float] = norm.rvs):
        self.underlying_noise_model = underlying_noise_model
        self.noise_size = noise_size
        self.noise_dist = noise_dist

    @abstractmethod
    def _apply(self,X,Y: float):
        pass

    def apply(self,X,Y: float) -> float:
        """Applies the noise model

        Args:
            X : The parameters that created the signal.
            Y (float): The signal to apply the noise to.

        Returns:
            float: The signal after the noise have been applied.
        """
        if self.underlying_noise_model is not None:
            # Moidfying the signal with the underlying model
            Y = self.underlying_noise_model.apply(X,Y)
        return self._apply(X,Y)
    
    @property
    def noise(self) -> float:
        """A raw noise value, to be used in the _apply() function"""
        return self.noise_dist()*self.noise_size
    
class AdditiveNoise(NoiseModel): # Should this be named ConstantNoise?
    """
    Noise model for constant noise.

    Parameters:
    * `noise_dist` [() -> float, default normal distribution]: The distribution of the
        noise.
    
    * `noise_size` [float, default 1]: The size of the noise. The noise added to the
        signal is noise_dist()*noise_size.

    * `underlying_noise_model` [NoiseModel | None, default None]: A noise model applied
        before applying the constant noise.
    """
    def __init__(self, noise_size: float = 1, **kwargs):
        super().__init__(noise_size=noise_size, **kwargs)

    def _apply(self,_,Y: float) -> float:
        return Y + self.noise

    
class MultiplicativeNoise(NoiseModel): # Should this be named ProportionalNoise?
    """
    Noise model for noise proportional to the signal

    Parameters:
    * `noise_dist` [() -> float, default normal distribution]: The distribution of the
        noise.
    
    * `noise_size` [float, default 0.01]: The size of the noise realtive to the signal.
        The noise added to the signal is noise_dist()*noise_size*signal.

    * `underlying_noise_model` [NoiseModel | None, default None]: A noise model applied
        before applying the proportional noise.
    """
    def __init__(self, noise_size : float = 1/100, **kwargs):
        super().__init__(noise_size=noise_size,**kwargs)

    def _apply(self,_,Y: float) -> float:
        return Y * (1+self.noise)
    
class DataDependentNoise(NoiseModel):
    """
    Noise model for noise that depends on the input parameters.

    Parameters:
    * `noise_models` [(parameters) -> NoiseModel]: A function that takes a set of
        parameters, and returns a noise model to apply.

    * `underlying_noise_model` [NoiseModel | None, default None]: A noise model applied
        before applying the additive noise.

    Examples:

    To make additive noise proportional to the input parameter (not to the score):
    ```
    noise_choice = lambda X: AdditiveNoise(noise_size=X)
    noise_model = DataDependentNoise(noise_models=noise_choice)
    ```

    To add additive noise except if X[0] is 0:
    ```
    noise_choice = lambda X: ZeroNoise() if X[0]==0 else AdditiveNoise()
    noise_model = DataDependentNoise(noise_models=noise_choice)
    ```
    """
    def __init__(self, noise_models: Callable[...,NoiseModel], **kwargs):
        self.noise_models = noise_models
        super().__init__(noise_size=0, **kwargs)

    def _apply(self,X,Y: float) -> float:
        return self.noise_models(X).apply(X,Y)
    
class ZeroNoise(NoiseModel):
    """Noise model for zero noise. Doesn't take any arguments. Exist for consistency,
    and to be used in data dependent noise models.
    """
    def __init__(self):
        super().__init__(noise_size=0)

    def _apply(self,_,Y: float) -> float:
        return Y


def noise_model_factory(type: str, **kwargs)-> NoiseModel:
    if type == "additive":
        return AdditiveNoise(**kwargs)
    elif type == "multiplicative":
        return MultiplicativeNoise(**kwargs)
    elif type == "zero":
        return ZeroNoise()
    else:
        raise ValueError(f"Noise model of type '{type}' not recognised")